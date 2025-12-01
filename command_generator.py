# command_generator.py
import math

def generate_commands(params):
    """
    根據設定參數生成指令列表。

    Args:
        params (dict): 從設定檔載入的參數字典。

    Returns:
        list: 包含所有指令字串的列表。
    """
    commands = []
    commands.append(f"$SMPD{params['smpd']}#")
    # commands.append("$WAIT2#")
    # 1. 回到原點
    commands.append("$ORI#")
    # commands.append(f"$WAIT{params['wait_time']}#")
    # 2. 開燈
    if params['autoscaling']==0:
        if params['lamp'] == 0:
            commands.append("$SLD0,1#")
            # commands.append("$WAIT2#")
        elif params['lamp'] == 1:
            commands.append("$SLD1,1#")
            # commands.append("$WAIT2#")
        elif params['lamp'] == 2:
            commands.append("$SLD0,1#")
            # commands.append("$WAIT2#")
            commands.append("$SLD1,1#")
            # commands.append("$WAIT2#")
    # commands.append(f"$WAIT2#")
    # 3. 等待
    commands.append(f"$WAIT{params['wait_time']}#")

    # 4. Offset 移動
    if params['offset'] > 0:
        offset_pulses = int(params['offset'] / params['pulse_distance'])

        if offset_pulses >= 5:
            commands.append(f"$MLS{offset_pulses}#")
            # commands.append("$WAIT15#")

    # 5. 循環量測
    pulses_per_point = params['no_of_pulse_per_point']
    for _ in range(params['no_of_point_per_cycle']):
        # 移動到下一個點
        if pulses_per_point >= 5:
            commands.append(f"$MLS{pulses_per_point}#")
        # 讀取光譜
        commands.append("$SRD#")
    # commands.append(f"$WAIT5#")
    commands.append("$WAIT2#")

    # 7. 最後回到原點
    commands.append("$ORI#")
    # commands.append("$WAIT20#")
    commands.append("$UARTLOOP#")
    commands.append("$WAIT2#")

    return commands
