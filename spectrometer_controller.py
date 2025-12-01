# spectrometer_controller.py
import ctypes
import time
from ctypes import c_void_p, c_int, byref
import logging
import cv2
import numpy as np
import json
import re
import os
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d
import pandas as pd


class SpectrometerController:
    """
    控制光譜儀的核心功能，精簡自 main_v1.5.py。
    """

    def __init__(self, gain=2, exp=300):
        self.dll_path = os.path.join('Dll', 'SpectroChipsControl.dll')
        if not os.path.exists(self.dll_path):
            raise FileNotFoundError(f"找不到光譜儀 DLL 檔案: {self.dll_path}")

        self.dll = ctypes.WinDLL(self.dll_path)
        self.gain = gain
        self.exp = exp
        self.WL = [0, 0, 0, 0]  # 波長校正係數
        self.ROI = 470  # 預設 ROI
        self.rows_number = 20  # 預設 ROI 寬度
        self.x_axis_wavelength = None
        self.cap = None

        self._initialize_functions()
        if self._initialize_device():
            self._read_device_settings()
            self._initialize_camera()
        else:
            raise RuntimeError("無法初始化光譜儀設備。")

    def _initialize_functions(self):
        """定義從 DLL 來的函數原型。"""
        self.SP_Initialize = self.dll.SP_Initialize
        self.SP_Initialize.argtypes = [c_void_p]
        self.SP_Initialize.restype = ctypes.wintypes.DWORD

        self.SP_Finalize = self.dll.SP_Finalize
        self.SP_Finalize.argtypes = [c_void_p]
        self.SP_Finalize.restype = ctypes.wintypes.DWORD

        self.SP_DataRead = self.dll.SP_DataRead
        self.SP_DataRead.argtypes = [c_void_p, ctypes.POINTER(c_int)]
        self.SP_DataRead.restype = ctypes.c_long

    def _initialize_device(self):
        """初始化光譜儀硬體。"""
        hr = self.SP_Initialize(None)
        if hr != 0:
            logging.error("光譜儀設備初始化失敗。")
            return False
        logging.info("光譜儀設備初始化成功。")
        return True

    def _read_device_settings(self):
        """從設備讀取設定，如 ROI 和波長係數。"""
        buffer_size = 4096
        buffer = (ctypes.c_ubyte * buffer_size)()
        data_length = c_int(buffer_size)
        result = self.SP_DataRead(buffer, byref(data_length))

        if result == 0:
            read_data = bytes(buffer[:data_length.value]).decode('utf-8', errors='ignore')
            cleaned_data = re.sub(r'[\x00\r\n]', '', read_data)
            try:
                json_data = json.loads(cleaned_data)
                self.ROI = int(json_data.get("roi_height", self.ROI))
                self.WL = [
                    float(json_data.get("conversion_factor_0_a0", 0)),
                    float(json_data.get("conversion_factor_0_a1", 0)),
                    float(json_data.get("conversion_factor_0_a2", 0)),
                    float(json_data.get("conversion_factor_0_a3", 0))
                ]
                self.x_axis_wavelength = [self.WL[0] + x * self.WL[1] + x ** 2 * self.WL[2] + x ** 3 * self.WL[3] for x
                                          in range(1280)]
                logging.info(f"成功從設備讀取設定。ROI: {self.ROI}, WL[0]: {self.WL[0]},WL[1]: {self.WL[1]},WL[2]: {self.WL[2]},WL[3]: {self.WL[3]}")
            except json.JSONDecodeError:
                logging.warning("讀取設備設定時 JSON 解碼失敗，將使用預設值。")
                self._generate_default_wavelength_axis()
        else:
            logging.error(f"從設備讀取資料失敗，錯誤碼: {result}")
            self._generate_default_wavelength_axis()

    def _generate_default_wavelength_axis(self):
        """如果無法從設備讀取，則生成一個預設的波長軸。"""
        # 這是一個示例，實際值應接近真實光譜儀
        start_wl, end_wl = 350, 1050
        self.x_axis_wavelength = np.linspace(start_wl, end_wl, 1280)
        logging.info("已生成預設波長軸。")

    def _initialize_camera(self):
        """初始化相機並設定參數。"""
        for i in range(5):  # 嘗試前5個索引
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                if width == 1280 and height == 800:
                    self.cap = cap
                    # 設定為原始模式並設定參數
                    self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
                    self.cap.set(cv2.CAP_PROP_GAIN, self.gain)
                    self.cap.set(cv2.CAP_PROP_BRIGHTNESS, self.exp)  # 在 OpenCV 中，曝光通常由 BRIGHTNESS 控制
                    logging.info(f"相機 {i} 初始化成功 (1280x800)。增益: {self.gain}, 曝光: {self.exp}")
                    return
                cap.release()
        raise RuntimeError("找不到符合解析度 (1280x800) 的光譜儀相機。")

    def set_exp(self, exp):
        """設定曝光參數。"""
        self.exp = exp
        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_BRIGHTNESS, self.exp)


    def _process_frame(self, frame):
        """處理從相機讀取的原始影格，轉換為光譜強度。"""
        # 將高位和低位資料提取並組合
        high_bits = frame[0][::2].astype(np.uint16)
        low_bits = frame[0][1::2].astype(np.uint16)
        # 確保 low_bits 長度一致
        if len(high_bits) > len(low_bits):
            low_bits = np.append(low_bits, 0)
        combined_data = ((high_bits << 4) | (low_bits - 128)).astype(np.uint16)
        return combined_data

    def read_spectrum_single(self):
        """
        捕獲一幀影像，並回傳處理後的光譜資料。

        Returns:
            numpy.ndarray: 1D 陣列 (長度 1280)，包含光譜強度值。
                           如果失敗則返回 None。
        """
        if not self.cap or not self.cap.isOpened():
            logging.error("相機未初始化或未開啟。")
            return None

        ret, frame = self.cap.read()
        if not ret or frame is None:
            logging.error("無法從相機讀取影格。")
            return None

        try:
            combined = self._process_frame(frame)
            result = combined.reshape(800, 1280).astype(np.float64)

            # 從 ROI 區域提取光譜並平均
            roi_data = result[self.ROI: self.ROI + self.rows_number, :]
            roi_avg = np.mean(roi_data, axis=0)
            # window_size = 79
            # poly = 3
            # roi_avg = savgol_filter(roi_avg, window_size, poly)
            return roi_avg
        except Exception as e:
            logging.error(f"處理光譜影格時發生錯誤: {e}", exc_info=True)
            return None

    def get_wavelength_axis(self):
        """返回波長軸數據"""
        if self.x_axis_wavelength is None:
            self._generate_default_wavelength_axis()
        return np.array(self.x_axis_wavelength)

    def finalize(self):
        """釋放所有資源。"""
        if self.cap and self.cap.isOpened():
            self.cap.release()
            logging.info("相機資源已釋放。")
        hr = self.SP_Finalize(None)
        if hr == 0:
            logging.info("光譜儀設備資源成功釋放。")
        else:
            logging.error("光譜儀設備資源釋放失敗。")

    def read_spectrum(self, no_of_average=1):
        """
        讀取多幀影像並平均，回傳處理後的光譜資料。

        Args:
            no_of_average (int): 要平均的幀數，預設為 1。

        Returns:
            numpy.ndarray: 1D 陣列 (長度 1280)，包含光譜強度值。
                           如果失敗則返回 None。
        """
        if no_of_average <= 0:
            logging.warning("平均次數必須大於 0。")
            return None
        # temp = self.read_spectrum_single()   #temp舍弃
        # temp = self.read_spectrum_single()   #temp舍弃

            # 使用一個列表來收集所有成功讀取的光譜
        spectrums = []
        for i in range(no_of_average):

            single_spectrum = self.read_spectrum_single()
            # time.sleep(0.1)
            # 關鍵：檢查單次讀取是否成功
            if single_spectrum is not None:
                spectrums.append(single_spectrum)
            else:
                # 如果有一次讀取失敗，可以選擇：
                # 1. 忽略這次失敗，繼續讀取下一次 (但最終平均的次數會少於 no_of_average)
                # 2. 中斷整個過程並返回失敗 (更嚴謹的做法)
                logging.error(f"在第 {i + 1}/{no_of_average} 次讀取光譜時失敗，中止平均過程。")
                return None  # 採用嚴謹做法，直接返回 None

        # 如果列表為空 (所有讀取都失敗了)
        if not spectrums:
            logging.error("沒有成功讀取到任何光譜數據。")
            return None

        # 將光譜列表轉換為 2D NumPy 陣列並計算平均值
        # np.array(spectrums) 會產生一個 (no_of_average, 1280) 的陣列
        # axis=0 會沿著第一個維度 (即沿著每一次的讀取) 計算平均值
        average_spectrum = np.mean(np.array(spectrums), axis=0)
        # window_size = 79
        # poly = 3
        # average_spectrum =savgol_filter(average_spectrum, window_size, poly)

        return average_spectrum

    def read_spectrum_single_no_base(self,params):
        raw_data = self.read_spectrum_single()
        wl = self.get_wavelength_axis()
        wl = np.array(wl)
        new_wl = np.arange(400, 1000.5, 0.5)
        raw_data = np.array(raw_data)
        # -------------------------

        f = interp1d(wl,raw_data,kind='linear')
        new_data = f(new_wl)
        s = pd.Series(new_data, index=new_wl)
        baseline_start = params['baseline_start']
        baseline_end = params['baseline_end']
        mask = (s.index >= baseline_start) & (s.index <= baseline_end)
        baseline_values = s[mask]
        avg = baseline_values.mean()
        s = s - avg
        return s

