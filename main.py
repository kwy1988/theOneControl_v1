# main.py
import serial
import time
import re
import numpy as np
import pandas as pd
from datetime import datetime
import os
import logging

# 導入自定義模組
import config_loader
import stage_controller
import spectrometer_controller
import command_generator
import data_processor
import excel_writer

# --- 日誌設定 ---
log_directory = "logs"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_directory, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")),
        logging.StreamHandler()
    ]
)


def get_com_port():
    """
    提示使用者輸入有效的 COM port。

    Returns:
        str: 使用者輸入的有效 COM port 字串 (例如, 'COM7')。
    """
    while True:
        port = input("請輸入 STM32 控制板的 COM port (格式為 COMx, 例如 COM7): ")
        if re.match(r'^COM\d+$', port):
            return port
        else:
            print("輸入格式錯誤，請確保 'COM' 為大寫且後面跟著數字。")


def get_config_path():
    """
    提示使用者輸入設定檔的路徑。

    Returns:
        str: 設定檔的有效路徑。
    """
    while True:
        # path = input("請輸入設定檔 (txt) 的完整路徑: ")
        path = './script.txt'
        if os.path.exists(path) and path.endswith('.txt'):
            return path
        else:
            print("路徑無效或檔案不是 .txt 檔，請重新輸入。")


def create_result_dataframe(params, intensity_data):
    """
    根據參數和強度數據創建一個 DataFrame。
    """
    num_points = params['no_of_point_per_cycle']

    if len(intensity_data) != num_points:
        logging.warning(f"強度數據的長度 ({len(intensity_data)}) 與量測點數 ({num_points}) 不符。將以較短者為準。")
        min_len = min(len(intensity_data), num_points)
        intensity_data = intensity_data[:min_len]
        num_points = min_len

    points = np.arange(1, num_points + 1)         #np矩陣
    offset_mm = params['offset']
    dist_per_point_mm = params['no_of_pulse_per_point'] * params['pulse_distance']
    cumulative_dist = np.cumsum(np.full(num_points, dist_per_point_mm))
    x_mm = offset_mm + cumulative_dist
    z_mm = points * params['distance_to_height'] * dist_per_point_mm + offset_mm * params['distance_to_height']

    return pd.DataFrame({
        'point': points,
        'X(mm)': x_mm,
        'Z(mm)': z_mm,
        'intensity': intensity_data
    })

def perform_autoscaling(params,stage, spectrometer):
    """
    自動調整光譜。
    """
    logging.info("正在進行自動調整光譜...")

    #1 initialize the parameter of autoscaling
    autoscaling_wavelength = params['autoscaling_wavelength']
    autoscaling_intensity = params['autoscaling_intensity']
    autoscaling_threshold = params['autoscaling_threshold']
    autoscaling_position = params['autoscaling_position']
    pulse_distance = params['pulse_distance']

    stage.send_command(f"$ORI#",15)

    #2 turn on the light and wait 15 seconds
    stage.send_command(f"$MLS{int(autoscaling_position/pulse_distance)}#",10)

    if params['lamp'] == 0:
        stage.send_command("$SLD0,1#",2)

        # commands.append("$WAIT2#")
    elif params['lamp'] == 1:
        stage.send_command("$SLD1,1#",2)

        # commands.append("$WAIT2#")
    elif params['lamp'] == 2:
        stage.send_command("$SLD0,1#",2)
        stage.send_command("$SLD1,1#",2)


    time.sleep(15)

    #3 autoscaling
    for i in range(20):
        logging.info(f"AutoScaling Iteration {i + 1}/20")
        raw_spec = spectrometer.read_spectrum_single()
        raw_spec = spectrometer.read_spectrum_single()
        raw_spec = spectrometer.read_spectrum_single()
        raw_spec = spectrometer.read_spectrum_single()
        raw_spec = spectrometer.read_spectrum_single_no_base(params)

        # wl = spectrometer.get_wavelength_axis()
        # ias_index = np.abs(wl - autoscaling_wavelength).argmin()
        ias = raw_spec.loc[autoscaling_wavelength]
        logging.info(f"Exp={spectrometer.exp}, Gain={spectrometer.gain}. Intensity at ~{autoscaling_wavelength}nm is {ias:.2f} (Target: {autoscaling_intensity})")

        if abs(ias - autoscaling_intensity) <= autoscaling_threshold:
            #3.1 start use number of autoscaling to calibrate the exposure time
            logging.info("AutoScaling converged.")
            # logging.info(f"AutoScaling  scan {params['number_of_autoscaling']} times")
            # if params['number_of_autoscaling'] == 0:
            #     pass
            # else:
                # intensity_list=[]
                # for j in range(params['number_of_autoscaling']):
                #     logging.info(f"AutoScaling scan {j + 1}/{params['number_of_autoscaling']}")
                #     stage.send_command(f"$MLS{params['no_of_pulse_per_point']}#")
                #     raw_spec = spectrometer.read_spectrum_single_no_base(params)
                #     # wl = spectrometer.get_wavelength_axis()
                #     # ias_index = np.abs(wl - autoscaling_wavelength).argmin()
                #     ias = raw_spec[autoscaling_wavelength]
                #     intensity_list.append(ias)
                # avg_intensity = sum(intensity_list) / len(intensity_list)
                # pias = autoscaling_intensity/avg_intensity
                # spectrometer.exp = min(int(spectrometer.exp * pias), 899)
                # spectrometer.exp = max(1, spectrometer.exp)
                # spectrometer.set_exp(spectrometer.exp)
                # logging.info(f"the exp after this autoscaling is {spectrometer.exp} ms")
                # raw_spec = spectrometer.read_spectrum_single()
                # raw_spec = spectrometer.read_spectrum_single()
                # raw_spec = spectrometer.read_spectrum_single()
                # raw_spec = spectrometer.read_spectrum_single()

            logging.info("AutoScaling over.")
            return True

        pias = autoscaling_intensity / ias if ias > 0 else 2  # Double exposure if intensity is zero
        spectrometer.exp = min(int(spectrometer.exp * pias), 899)  # Cap exposure at 1000ms
        spectrometer.exp = max(1, spectrometer.exp)  # Minimum exposure is 1ms
        spectrometer.set_exp(spectrometer.exp)

    logging.error("AutoScaling failed to converge after 20 iterations.")
    while True:
        try:
            spectrometer.exp = input("AutoScaling failed. Please manually enter Exposure time (ms): ")
            logging.info(f"Using manually set Exposure: {spectrometer.exp}ms")

            return True
        except ValueError:
            print("Invalid input. Please enter an integer.")

def perform_autoscaling2(params, stage, spectrometer):
    logging.info("！！！正在多點平均自動調整光譜...")

    # 1 initialize the parameter of autoscaling
    autoscaling_wavelength = params['autoscaling_wavelength']
    autoscaling_intensity = params['autoscaling_intensity']
    autoscaling_threshold = params['autoscaling_threshold']
    autoscaling_position = params['autoscaling_position']
    pulse_distance = params['pulse_distance']
    #4 turn off the light and move to ORI
    # stage.send_command(f"$ORI#",15)
    # stage.send_command(f"$MLS{int(autoscaling_position / pulse_distance)}#", 15)

    if params['number_of_autoscaling'] == 0:
        return
    else:
        ii=0
        while True:
            ii=ii+1
            intensity_list=[]
            stage.send_command(f"$ORI#", 15)
            stage.send_command(f"$MLS{int(autoscaling_position / pulse_distance)}#", 15)
            for j in range(params['number_of_autoscaling']):
                logging.info(f"Average AutoScaling scan {j + 1}/{params['number_of_autoscaling']}")
                stage.send_command(f"$MLS{params['no_of_pulse_per_point']}#")
                raw_spec = spectrometer.read_spectrum_single_no_base(params)
                # wl = spectrometer.get_wavelength_axis()
                # ias_index = np.abs(wl - autoscaling_wavelength).argmin()
                ias = raw_spec[autoscaling_wavelength]
                logging.info(f"intensity is {ias}, at {j+1} point")
                intensity_list.append(ias)
            avg_intensity = sum(intensity_list) / len(intensity_list)
            logging.info(f"the average intensity of autoscaling points is {avg_intensity}")
            if abs(avg_intensity-autoscaling_intensity)<=autoscaling_threshold:
                logging.info("successful AutoScaling in average points")
                return
            else:
                logging.info("bias is big, tune the exp")
                pias = autoscaling_intensity/avg_intensity
                logging.info(f"the previous exp is {spectrometer.exp} ms")
                spectrometer.exp = min(int(spectrometer.exp * pias), 899)
                spectrometer.exp = max(1, spectrometer.exp)
                spectrometer.set_exp(spectrometer.exp)
            # logging.info(f"the average intensity of autoscaling points is {avg_intensity}")
                logging.info(f"the exp after this autoscaling is {spectrometer.exp} ms")
            raw_spec = spectrometer.read_spectrum_single()
            raw_spec = spectrometer.read_spectrum_single()
            raw_spec = spectrometer.read_spectrum_single()
            raw_spec = spectrometer.read_spectrum_single()
            # raw_spec = spectrometer.read_spectrum_single_no_base(params)
            # ias = raw_spec[autoscaling_wavelength]
            # logging.info(f"intensity is {ias}, after the {ii}th time of autoscaling")
            # if abs(ias-params['autoscaling_intensity'])<params['autoscaling_threshold']:
            #     logging.info("successful AutoScaling in average points")
            #     break
            # else:
            #     logging.info(f"continue next average autoscaling")
            #     continue




def main():
    """
    主執行函數
    """
    stage = None
    spectrometer = None
    try:
        # 1. 獲取使用者輸入
        com_port = get_com_port()
        config_path = get_config_path()

        # 2. 載入並驗證設定
        logging.info(f"從 {config_path} 載入設定...")
        params = config_loader.load_and_validate_config(config_path)
        logging.info("設定檔載入並驗證成功。")
        logging.info(f"參數: {params}")

        # 3. 初始化控制器
        logging.info(f"正在連接控制器於 {com_port}...")
        # 快速模式切換：將 fast_mode 設為 True 來啟用
        stage = stage_controller.StageController(port=com_port, fast_mode=False)
        logging.info("控制器連接成功。")

        logging.info("正在初始化光譜儀...")
        spectrometer = spectrometer_controller.SpectrometerController(gain=params['gain'], exp=params['exp'])
        logging.info("光譜儀初始化成功。")


        if params['autoscaling']==1:
            perform_autoscaling(params, stage, spectrometer)
            perform_autoscaling2(params, stage, spectrometer)



        params['exp_after_autoscaling']=spectrometer.exp
        # 4. 生成單一循環的指令列表
        logging.info("正在生成單一循環的指令腳本...")
        command_list = command_generator.generate_commands(params)

        # 保存指令腳本
        timestamp = datetime.now().strftime('%Y%m%d%H%M')
        command_filename = os.path.join(params['filepath'], f"{timestamp}_command.txt")
        with open(command_filename, 'w') as f:
            f.write("# --- 此為單一循環的指令腳本 ---\n")
            for cmd in command_list:
                f.write(f"{cmd}\n")
        logging.info(f"單一循環的指令腳本已生成並保存至: {command_filename}")

        # 5. 根據 np_of_cycle 執行多個循環的量測
        all_cycles_data = {}
        total_data_for_last_cycle = None
        for cycle_num in range(1, params['np_of_cycle'] + 1):
            logging.info(f"========== 開始執行循環 {cycle_num}/{params['np_of_cycle']} ==========")

            spectral_data = np.zeros((1280, params['no_of_point_per_cycle']))
            srd_count = 0


            for i, command in enumerate(command_list):
                logging.info(f"循環 {cycle_num} - 執行指令 {i + 1}/{len(command_list)}: {command}")

                if command.startswith('$WAIT'):
                    wait_time = int(re.search(r'\d+', command).group())
                    logging.info(f"等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                elif command == '$SRD#':
                    # 在快速模式下，我們需要手動為光譜量測增加延遲
                    # 確保上一個移動指令有足夠的時間完成。
                    # 這個延遲時間需要根據實驗猜測和調整，非常不可靠。
                    time.sleep(0.2)  # !危險的延遲，需要手動調整!
                    if srd_count < params['no_of_point_per_cycle']:
                        for _ in range(params['no_of_drop']):
                            spectrometer.read_spectrum_single()
                        spectrum = spectrometer.read_spectrum(params['no_of_average'])
                        time.sleep(0.2)
                        if spectrum is not None:
                            spectral_data[:, srd_count] = spectrum
                            srd_count += 1
                        else:
                            logging.error("讀取光譜失敗。")
                    else:
                        logging.warning("偵測到額外的 $SRD# 指令，已達最大量測點數，將跳過。")
                elif command=='$ORI#':
                    stage.send_command(command,15)
                elif command.startswith('$MLS') and int(command[4:-1])>20:
                    stage.send_command(command, 15)
                else:  # STM32 指令
                    stage.send_command(command)

            logging.info(f"---------- 循環 {cycle_num} 量測流程執行完畢 ----------")

            # 該循環的資料處理
            logging.info(f"開始為循環 {cycle_num} 進行資料後處理...")

            processed_intensity, total_data_for_cycle = data_processor.process_spectral_data(
                spectral_data,
                spectrometer.get_wavelength_axis(),
                params['sampling_wavelength'],
                params
            )
            logging.info(f"循環 {cycle_num} 資料後處理完成。")

            # 將此循環的結果存儲起來
            sheet_name = f"cycle_{cycle_num}"
            df = create_result_dataframe(params, processed_intensity)
            all_cycles_data[sheet_name] = df

            sheet_name = f"total_data_{cycle_num}"
            if total_data_for_cycle is not None:
                logging.info("正在將完整光譜數據轉換為 DataFrame...")
                new_wavelengths = np.arange(400, 960.5, 0.5)
                point_headers = [f'Point_{i + 1}' for i in range(total_data_for_cycle.shape[1])]
                headers = ['Wavelength'] + point_headers
                data_to_write = np.hstack([new_wavelengths[:, np.newaxis], total_data_for_cycle])
                total_data_df = pd.DataFrame(data_to_write, columns=headers)
                all_cycles_data[sheet_name] = total_data_df

        if params['lamp'] == 0:
            stage.send_command("$SLD0,0#")
        elif params['lamp'] == 1:
            stage.send_command("$SLD1,0#")
        elif params['lamp'] == 2:
            stage.send_command("$SLD0,0#")
            # commands.append("$WAIT2#")
            stage.send_command("$SLD1,0#")



        # 6. 將所有循環的結果寫入單一 Excel 檔案
        excel_filename = os.path.join('.\\', f"{timestamp}_result.xlsx")
        logging.info(f"正在將所有循環的結果寫入 Excel: {excel_filename}")
        excel_writer.write_to_excel(
            all_cycles_data=all_cycles_data,
            output_path=excel_filename,
            params=params
        )
        logging.info("Excel 報告生成成功！")

    except (ValueError, FileNotFoundError, RuntimeError, serial.SerialException) as e:
        logging.error(f"發生錯誤: {e}")
    except Exception as e:
        logging.error(f"發生未預期的錯誤: {e}", exc_info=True)
    finally:
        # 7. 資源釋放
        if stage and stage.is_open():
            stage.close()
            logging.info("序列埠已關閉。")
        if spectrometer:
            spectrometer.finalize()
            logging.info("光譜儀資源已釋放。")
        logging.info("程序結束。")


if __name__ == "__main__":
    main()