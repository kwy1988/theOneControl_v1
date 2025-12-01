# stage_controller.py
import serial
import time
import logging
import config_loader


class StageController:
    """
    控制 STM32 舞台移動的類別。
    """

    def __init__(self, port, baud_rate=38400, timeout=2, max_retries=3, fast_mode=False):
        """
        初始化序列埠連接。

        Args:
            port (str): COM port 名稱 (例如 'COM7')。
            baud_rate (int): 波特率。
            timeout (int): 讀取超時時間（秒）。
            max_retries (int): 指令失敗時的最大重試次數。
            fast_mode (bool): 是否啟用快速模式（不等待回應）。
        """
        self.port = port
        self.baud_rate = baud_rate
        self.default_timeout = timeout
        self.max_retries = max_retries
        self.fast_mode = fast_mode
        self.ser = None

        # 在快速模式下，我們不使用 pyserial 的超時機制，而是手動延遲
        serial_timeout = 0.1 if self.fast_mode else self.default_timeout

        try:
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=serial_timeout)
            logging.info(f"成功打開序列埠 {self.port}")
            if self.fast_mode:
                logging.warning("=" * 50)
                logging.warning("警告：控制器已啟用『快速模式』！")
                logging.warning("程式將不會等待硬體回應，可能導致數據不準確或丟失！")
                logging.warning("請僅在完全了解風險的情況下使用。")
                logging.warning("=" * 50)
        except serial.SerialException as e:
            logging.error(f"無法打開序列埠 {self.port}: {e}")
            raise

    def send_command(self, command, timeout=None):
        """
        向 STM32 發送指令。
        在正常模式下，會等待並驗證回應。
        在快速模式下，會直接發送並假設成功。
        Args:
            command (str): 要發送的指令。
            timeout (int, optional): 本次指令專用的超時時間（秒）。
                                     如果為 None，則使用初始化時的預設超時時間。
        """
        if not self.ser or not self.ser.is_open:
            logging.error("序列埠未開啟，無法發送指令。")
            return "ERROR: Port not open"

        # ----- 快速模式 -----
        if self.fast_mode:
            try:
                self.ser.write(command.encode('ascii'))
                # 在發送後做一個極短的延遲，稍微降低緩衝區溢位的風險
                # 但這不能保證同步
                time.sleep(0.5)
                return "$OK#"  # 直接假設成功
            except Exception as e:
                logging.error(f"快速模式下發送指令時發生錯誤: {e}")
                return "$NACK#"  # 假設失敗

        # ----- 正常（可靠）模式 -----
        self.ser.timeout = self.default_timeout

            # 如果此指令有指定特殊的 timeout，就臨時修改它
        if timeout is not None:
            self.ser.timeout = timeout
            logging.debug(f"臨時將 timeout 設為 {timeout} 秒，用於指令 '{command}'")

        retries = 0
        while retries <= self.max_retries:
            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()

                logging.debug(f"發送指令: {command.encode('ascii')}")
                self.ser.write(command.encode('ascii'))

                # readline() 將會使用當前 self.ser.timeout 的設定
                response = self.ser.readline().decode('ascii').strip()

                if command == "$UARTLOOP#":
                    if timeout is not None:
                        self.ser.timeout = self.default_timeout
                        logging.debug(f"恢復 timeout 為預設值: {self.default_timeout} 秒")
                    return "STM32 work properly" if response == "$UARTLOOP#" else "STM32 work not properly"

                if response == "$OK#":
                    if timeout is not None:
                        self.ser.timeout = self.default_timeout
                        logging.debug(f"恢復 timeout 為預設值: {self.default_timeout} 秒")
                    return response
                elif response == "$NACK#":
                    logging.warning(f"收到 NACK 回應，第 {retries + 1} 次重試...")
                    retries += 1
                    time.sleep(0.5)
                elif not response:
                    # 使用當前的 timeout 值來顯示錯誤訊息
                    current_timeout = self.ser.timeout
                    logging.error(f"指令執行超時（{current_timeout}秒內未收到回應）。")
                    if retries < self.max_retries:
                        logging.warning(f"第 {retries + 1} 次重試...")
                    retries += 1
                else:
                    logging.error(f"收到未知的回應: {response}")
                    retries += 1
                    time.sleep(0.5)

            except serial.SerialException as e:
                logging.error(f"序列埠通訊錯誤: {e}")
                return "ERROR: SerialException"
            except Exception as e:
                logging.error(f"發送指令時發生未知錯誤: {e}")
                return "ERROR: Exception"
        logging.error(f"指令 '{command}' 在 {self.max_retries} 次重試後仍然失敗。")
        return "$NACK#"



        # retries = 0
        # while retries <= self.max_retries:
        #     try:
        #         self.ser.reset_input_buffer()
        #         self.ser.reset_output_buffer()
        #
        #         logging.debug(f"發送指令: {command.encode('ascii')}")
        #         self.ser.write(command.encode('ascii'))
        #
        #         response = self.ser.readline().decode('ascii').strip()
        #         if command == "$UARTLOOP#":
        #             if response == "$UARTLOOP#":
        #                 return "STM32 work properly"
        #             else:
        #                 return "STM32 work not properly"
        #         if response == "$OK#":
        #             return response
        #         elif response == "$NACK#":
        #             logging.warning(f"收到 NACK 回應，第 {retries + 1} 次重試...")
        #             retries += 1
        #             time.sleep(0.5)
        #         elif not response:
        #             logging.error(f"指令執行超時（{self.timeout}秒內未收到回應）。")
        #             if retries < self.max_retries:
        #                 logging.warning(f"第 {retries + 1} 次重試...")
        #             retries += 1
        #         else:
        #             logging.error(f"收到未知的回應: {response}")
        #             retries += 1
        #             time.sleep(0.5)
        #             # return f"ERROR: Unknown response {response}"
        #
        #     except serial.SerialException as e:
        #         logging.error(f"序列埠通訊錯誤: {e}")
        #         return "ERROR: SerialException"
        #     except Exception as e:
        #         logging.error(f"發送指令時發生未知錯誤: {e}")
        #         return "ERROR: Exception"
        #
        # logging.error(f"指令 '{command}' 在 {self.max_retries} 次重試後仍然失敗。")
        # return "$NACK#"

    def is_open(self):
        """檢查序列埠是否開啟。"""
        return self.ser and self.ser.is_open

    def close(self):
        """關閉序列埠連接。"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logging.info(f"序列埠 {self.port} 已關閉。")
