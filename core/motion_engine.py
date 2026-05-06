from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MotionState:
    alpha: float = 1.0
    x: float | None = None
    y: float | None = None
    scale: float = 1.0


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def ease(progress: float, easing: str = "linear") -> float:
    p = clamp(progress)
    if easing == "ease-in":
        return p * p
    if easing == "ease-out":
        return 1.0 - (1.0 - p) * (1.0 - p)
    if easing == "ease-in-out":
        return 2.0 * p * p if p < 0.5 else 1.0 - pow(-2.0 * p + 2.0, 2.0) / 2.0
    return p


def progress_at(t: float, start_time: float, duration: float, easing: str = "linear") -> float:
    if duration <= 0:
        return 1.0
    return ease((t - start_time) / duration, easing)


def state_at(
    preset: str,
    t: float,
    start_time: float,
    duration: float,
    target_x: float,
    target_y: float,
    base_opacity: float = 1.0,
    easing: str = "linear",
) -> MotionState:
    p = progress_at(t, start_time, duration, easing)
    if t < start_time:
        p = 0.0
    if preset == "fade":
        return MotionState(alpha=base_opacity * p, x=target_x, y=target_y)
    if preset == "slide":
        return MotionState(alpha=base_opacity, x=-200.0 + (target_x + 200.0) * p, y=target_y)
    if preset == "zoom":
        return MotionState(alpha=base_opacity, x=target_x, y=target_y, scale=1.3 - 0.3 * p)
    if preset == "bounce":
        overshoot = 1.0 + 0.15 * (1.0 - p) if p < 1.0 else 1.0
        return MotionState(alpha=base_opacity, x=target_x, y=target_y, scale=overshoot)
    return MotionState(alpha=base_opacity, x=target_x, y=target_y)


def ffmpeg_progress_expr(start: float, duration: float, easing: str = "linear") -> str:
    raw = f"clip((t-{start})/{max(duration, 0.001)},0,1)"
    if easing == "ease-in":
        return f"pow({raw},2)"
    if easing == "ease-out":
        return f"1-pow(1-{raw},2)"
    if easing == "ease-in-out":
        return f"if(lt({raw},0.5),2*pow({raw},2),1-pow(-2*{raw}+2,2)/2)"
    return raw


def alpha_expr(start: float, duration: float, opacity: float, preset: str, easing: str = "linear") -> str:
    if preset != "fade":
        return f"{opacity}"
    p = ffmpeg_progress_expr(start, duration, easing)
    return f"if(lt(t,{start}),0,{opacity}*{p})"


def x_expr(start: float, duration: float, target_x: float, preset: str, easing: str = "linear") -> str:
    if preset != "slide":
        return f"{target_x}"
    p = ffmpeg_progress_expr(start, duration, easing)
    return f"if(lt(t,{start}),-w,-w+({target_x}+w)*{p})"


def scale_expr(start: float, duration: float, base_scale: float, preset: str, easing: str = "linear") -> str:
    p = ffmpeg_progress_expr(start, duration, easing)
    if preset == "zoom":
        return f"{base_scale}*(1+0.3*(1-{p}))"
    if preset == "bounce":
        return f"{base_scale}*(1+0.15*(1-{p})*abs(sin({p}*PI*3)))"
    return f"{base_scale}"
