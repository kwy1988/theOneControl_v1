# config_loader.py
import os
import logging


def load_and_validate_config(filepath):
    """
    從指定的 .txt 檔案載入、解析並驗證設定參數。

    Args:
        filepath (str): 設定檔的路徑。

    Returns:
        dict: 包含已驗證參數的字典。

    Raises:
        FileNotFoundError: 如果檔案路徑不存在。
        ValueError: 如果任何參數無效。
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"設定檔不存在: {filepath}")

    params = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                key, value = line.split('=', 1)
                params[key.strip()] = value.strip()
            except ValueError:
                logging.warning(f"無法解析此行，已跳過: {line}")

    # --- 參數驗證 ---
    # swpd
    try:
        smpd = int(params['smpd'])
        if not (4 <= smpd <= 20):
            raise ValueError("smpd 值必須是 4 到 20 之間的整數")
        params['smpd'] = smpd
    except (ValueError, KeyError):
        raise ValueError("smpd 有誤，必須為 4 到 20 的整數。")
    # gain
    try:
        gain = int(params['gain'])
        if not (1 <= gain <= 32):
            raise ValueError("gain 值必須是 1 到 32 之間的整數。")
        params['gain'] = gain
    except (ValueError, KeyError):
        raise ValueError("gain 有誤，必須為 1 到 32 的整數。")

    # exp
    try:
        params['exp'] = int(params['exp'])
    except (ValueError, KeyError):
        raise ValueError("exp 有誤，必須是整數。")

    # sampling_wavelength
    try:
        params['sampling_wavelength'] = int(params['sampling_wavelength'])
    except (ValueError, KeyError):
        raise ValueError("sampling_wavelength 有誤，必須是整數。")

    # pulse_distance
    try:
        pulse_distance = float(params['pulse_distance'])
        if pulse_distance != 0.0196:
            raise ValueError("pulse_distance 必須是 0.0196。")
        params['pulse_distance'] = pulse_distance
    except (ValueError, KeyError):
        raise ValueError("pulse_distance 有誤，必須是 0.0196。")

    # no_of_pulse_per_point
    try:
        params['no_of_pulse_per_point'] = int(params['no_of_pulse_per_point'])
    except (ValueError, KeyError):
        raise ValueError("no_of_pulse_per_point 不是整數。")

    # no_of_point_per_cycle
    try:
        params['no_of_point_per_cycle'] = int(params['no_of_point_per_cycle'])
    except (ValueError, KeyError):
        raise ValueError("no_of_point_per_cycle 有誤，必須是整數。")

    # np_of_cycle
    try:
        np_of_cycle = int(params['np_of_cycle'])
        if np_of_cycle < 1:
            raise ValueError("np_of_cycle 必須是至少為 1 的整數。")
        params['np_of_cycle'] = np_of_cycle
    except (ValueError, KeyError):
        raise ValueError("np_of_cycle 有誤，必須是至少為 1 的整數。")

    # offset
    try:
        params['offset'] = float(params['offset'])
    except (ValueError, KeyError):
        raise ValueError("offset 有誤，必須是數字。")

    # wait_time
    try:
        wait_time = int(params['wait_time'])
        if wait_time <= 0:
            raise ValueError("wait_time 必須是正整數。")
        params['wait_time'] = wait_time
    except (ValueError, KeyError):
        raise ValueError("wait_time 有誤，必須是大於 0 的整數。")

    # lamp

    lamp = int(params['lamp'])

    params['lamp'] = lamp


    # filepath
    filepath_val = params.get('filepath')
    if not filepath_val or not os.path.isdir(filepath_val):
        raise ValueError(f"filepath 路徑無效或不存在: {filepath_val}")

    # distance_to_height
    try:
        params['distance_to_height'] = float(params['distance_to_height'])
    except (ValueError, KeyError):
        raise ValueError("distance_to_height 有誤，必須是數字。")

    try:
        no_of_average = int(params['no_of_average'])
        if not (1 <= no_of_average <= 32):
            raise ValueError("no_of_average 值必須是 1 到 100 之間的整數。")
        params['no_of_average'] = no_of_average
    except (ValueError, KeyError):
        raise ValueError("no_of_average 有誤，必須為 1 到 32 的整數。")

    try:
        no_of_drop = int(params['no_of_drop'])
        if not (1 <= no_of_drop <= 32):
            raise ValueError("no_of_drop 值必須是 1 到 100 之間的整數。")
        params['no_of_drop'] = no_of_drop
    except (ValueError, KeyError):
        raise ValueError("no_of_drop 有誤，必須為 1 到 32 的整數。")


    baseline_start = int(params['baseline_start'])
    params['baseline_start'] = baseline_start

    baseline_end = int(params['baseline_end'])
    params['baseline_end'] = baseline_end

    autoscaling = int(params['autoscaling'])
    params['autoscaling'] = autoscaling

    autoscaling_wavelength = int(params['autoscaling_wavelength'])
    params['autoscaling_wavelength'] = autoscaling_wavelength

    autoscaling_intensity = int(params['autoscaling_intensity'])
    params['autoscaling_intensity'] = autoscaling_intensity

    autoscaling_threshold = int(params['autoscaling_threshold'])
    params['autoscaling_threshold'] = autoscaling_threshold

    autoscaling_position = int(params['autoscaling_position'])
    params['autoscaling_position'] = autoscaling_position

    number_of_autoscaling = int(params['number_of_autoscaling'])
    params['number_of_autoscaling'] = number_of_autoscaling

    return params