from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MotionState:
    alpha: float = 1.0
    x: float = 0.0
    y: float = 0.0
    scale: float = 1.0
    rotation: float = 0.0


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def ease(progress: float, easing: str = "linear") -> float:
    p = clamp(progress)
    if easing == "ease-in":
        return p * p
    if easing == "ease-out":
        return 1 - (1 - p) * (1 - p)
    if easing == "ease-in-out":
        return 2 * p * p if p < 0.5 else 1 - ((-2 * p + 2) ** 2) / 2
    return p


def progress_at(t: float, start: float, duration: float, easing: str = "linear") -> float:
    if duration <= 0:
        return 1.0
    return ease((t - start) / duration, easing)


def state_at(preset: str, t: float, start: float, duration: float, x: float, y: float, opacity: float = 1.0, easing: str = "linear") -> MotionState:
    p = 0.0 if t < start else progress_at(t, start, duration, easing)
    if preset == "fade_in":
        return MotionState(opacity * p, x, y)
    if preset == "fade_out":
        return MotionState(opacity * (1 - p), x, y)
    if preset == "slide_left":
        return MotionState(opacity, x + 240 * (1 - p), y)
    if preset == "slide_right":
        return MotionState(opacity, x - 240 * (1 - p), y)
    if preset == "slide_up":
        return MotionState(opacity, x, y + 180 * (1 - p))
    if preset == "slide_down":
        return MotionState(opacity, x, y - 180 * (1 - p))
    if preset == "zoom_in":
        return MotionState(opacity, x, y, 0.75 + 0.25 * p)
    if preset == "zoom_out":
        return MotionState(opacity, x, y, 1.25 - 0.25 * p)
    if preset == "bounce":
        return MotionState(opacity, x, y, 1 + 0.16 * (1 - p) * abs(__import__("math").sin(p * 9.42)))
    if preset == "pop":
        return MotionState(opacity, x, y, 0.2 + 0.8 * p if p < 1 else 1)
    return MotionState(opacity, x, y)


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
    p = ffmpeg_progress_expr(start, duration, easing)
    if preset == "fade_in":
        return f"if(lt(t,{start}),0,{opacity}*{p})"
    if preset == "fade_out":
        return f"{opacity}*(1-{p})"
    return f"{opacity}"


def x_expr(start: float, duration: float, x: float, preset: str, easing: str = "linear") -> str:
    p = ffmpeg_progress_expr(start, duration, easing)
    if preset == "slide_left":
        return f"{x}+240*(1-{p})"
    if preset == "slide_right":
        return f"{x}-240*(1-{p})"
    return f"{x}"


def y_expr(start: float, duration: float, y: float, preset: str, easing: str = "linear") -> str:
    p = ffmpeg_progress_expr(start, duration, easing)
    if preset == "slide_up":
        return f"{y}+180*(1-{p})"
    if preset == "slide_down":
        return f"{y}-180*(1-{p})"
    return f"{y}"


def scale_expr(start: float, duration: float, scale: float, preset: str, easing: str = "linear") -> str:
    p = ffmpeg_progress_expr(start, duration, easing)
    if preset == "zoom_in":
        return f"{scale}*(0.75+0.25*{p})"
    if preset == "zoom_out":
        return f"{scale}*(1.25-0.25*{p})"
    if preset == "bounce":
        return f"{scale}*(1+0.16*(1-{p})*abs(sin({p}*PI*3)))"
    if preset == "pop":
        return f"{scale}*(0.2+0.8*{p})"
    return f"{scale}"
