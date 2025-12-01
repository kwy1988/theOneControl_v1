# data_processor.py
import numpy as np
from scipy.interpolate import interp1d
import logging



def process_spectral_data(spectral_data, original_wavelengths, sampling_wavelength,config):
    """
    處理原始光譜數據。
    包括波長轉換、內插和基線校正。

    Args:
        spectral_data (numpy.ndarray): 原始光譜數據 (1280 x N)。
        original_wavelengths (numpy.ndarray): 原始的波長軸 (長度 1280)。
        sampling_wavelength (int): 用於最終輸出的採樣波長。

    Returns:
        numpy.ndarray: 1D 陣列，包含在採樣波長下的強度值。
        :param config:
    """
    num_points = spectral_data.shape[1]
    logging.info(f"開始處理 {num_points} 個點的光譜數據。")

    # 1. 定義新的目標波長軸 (400 到 960 nm，間隔 0.5 nm)
    new_wavelengths = np.arange(400, 960.5, 0.5)

    # 準備一個矩陣來存儲內插和基線校正後的數據
    processed_data = np.zeros((len(new_wavelengths), num_points))

    for i in range(num_points):
        # 獲取當前 column 的光譜
        current_spectrum = spectral_data[:, i]

        # 2. 內插
        # 建立內插函數
        interp_func = interp1d(original_wavelengths, current_spectrum, kind='linear', bounds_error=False, fill_value=0)
        # 在新的波長軸上進行內插
        interpolated_spectrum = interp_func(new_wavelengths)

        # 3. 基線校正 (減去 950-960 nm 的平均值)
        baseline_mask = (new_wavelengths >= config['baseline_start']) & (new_wavelengths <= config['baseline_end'])
        if np.any(baseline_mask):
            baseline_value = np.mean(interpolated_spectrum[baseline_mask])
            corrected_spectrum = interpolated_spectrum - baseline_value
        else:
            logging.warning(f"在點 {i + 1} 中找不到 950-960nm 的數據來計算基線，將不進行校正。")
            corrected_spectrum = interpolated_spectrum

        processed_data[:, i] = corrected_spectrum

    # 4. 根據 sampling_wavelength 提取強度值
    # 找到最接近 sampling_wavelength 的索引
    sampling_index = np.argmin(np.abs(new_wavelengths - sampling_wavelength))
    final_intensity_values = processed_data[sampling_index, :]

    logging.info(f"在波長 {new_wavelengths[sampling_index]:.2f}nm (最接近 {sampling_wavelength}nm) 處提取強度值。")

    return final_intensity_values, processed_data