"""第 58 批：角色从斜坡走到台阶，前脚掌埋进地面，后脚又悬空，跑起来还一抽一抽...

修复点对应：
- lowest_foot       多点采样：脚掌多点取最低，斜坡前后高度差不再漏采
- pelvis_offset     骨盆求解：按腿长与当前姿势动态求骨盆偏移，不再固定值
- biped_balance     双足联合：左右脚共同求解，避免互相拉扯
- stair_ray_hits    台阶射线组：多射线命中统计，台阶边缘不再漏检
- platform_velocity 平台速度继承：脚继承移动平台速度，电梯上不再打滑
- root_motion_weight 根运动分层：根运动与 IK 权重共存，动画不再覆盖 IK
- knee_limit        膝盖限制：关节角钳制，防止膝盖反向弯
- speed_smooth      速度自适应：按速度比例给平滑权重，高速脚掌不抖
- contact_sync      接触点同步：本地/远端接触点收敛，网络落脚点一致
- normal_align      法线对齐：地形坡度参与脚掌旋转，斜坡贴面
- event_lock        事件帧锁定：阈值内吸附关键帧，压缩后不错位
- lod_ik_weight     LOD 过渡：权重随距离线性衰减，远近切换不跳
"""


def _clamp01(value):
    """把权重钳制在 [0, 1]。"""
    return max(0.0, min(1.0, value))


def lowest_foot(samples):
    """多点采样：返回脚掌最低采样点（最小高度）。

    脚底中心单射线采不到斜坡前后高度差，多点采样后取最保守的最低点，
    保证前脚掌不会埋进地面。
    """
    if not samples:
        raise ValueError("samples 不能为空：至少需要一个脚底采样点")
    return min(samples)


def pelvis_offset(leg_length, current):
    """骨盆求解：返回让脚能够到地面所需的骨盆高度偏移（腿长 - 当前高度）。

    取代固定偏移：腿长或姿势变化后按实际差值抬/降骨盆。
    """
    return leg_length - current


def biped_balance(left, right):
    """双足联合：左右脚共同求解，返回平衡高度（两脚高度均值）。

    双脚取同一折中高度，避免各自独立求解时互相拉扯。
    """
    return (left + right) * 0.5


def stair_ray_hits(hits):
    """台阶射线组：统计射线组中的命中数，空射线组返回 0。

    单射线会漏检台阶边缘，多射线命中数用于判断台阶轮廓。
    """
    return sum(1 for hit in hits if hit)


def platform_velocity(base, platform):
    """平台速度继承：脚的世界速度 = 角色相对速度 + 移动平台速度。

    电梯/移动平台把自身速度传给脚，角色不再在平台上滑动。
    """
    return base + platform


def root_motion_weight(root_weight, ik_weight):
    """根运动分层：返回根运动与 IK 共存时的有效权重（两者取小并钳制）。

    IK 只在根运动未完全占主导的区间生效，动画播放不再整体覆盖 IK。
    """
    return _clamp01(min(root_weight, ik_weight))


def knee_limit(angle, max_angle):
    """膝盖限制：把膝盖弯曲角钳制在 [0, max_angle]，防止反向弯/过伸。"""
    return max(0.0, min(angle, max_angle))


def speed_smooth(speed, max_speed):
    """速度自适应：按速度占比返回平滑权重，超速截断为 1，静止为 0。

    速度越快平滑权重越高，滤波窗口随之加大，高速奔跑时脚掌不再抖。
    """
    if max_speed <= 0:
        return 1.0 if speed > 0 else 0.0
    return _clamp01(speed / max_speed)


def contact_sync(local, remote):
    """接触点同步：本地与远端接触点取均值收敛，保证网络双方落脚点一致。"""
    return (local + remote) * 0.5


def normal_align(angle, slope):
    """法线对齐：在当前脚掌角度上叠加地形坡度修正，使脚掌贴合斜坡。"""
    return angle + slope


def event_lock(event_time, key_time, threshold):
    """事件帧锁定：事件时间落在关键帧阈值内时吸附到关键帧，否则原样返回。

    动画压缩后脚部锁定事件会错位，阈值内吸附可消除落脚点漂移。
    """
    if abs(event_time - key_time) <= threshold:
        return key_time
    return event_time


def lod_ik_weight(distance, max_distance):
    """LOD 过渡：IK 权重随距离线性衰减，近端为 1、远端为 0。

    远端仍输出连续衰减的权重而非硬切，近远 LOD 切换时脚不跳。
    """
    if max_distance <= 0:
        return 0.0
    return _clamp01(1.0 - distance / max_distance)
