"""图片版数字人：Q 版灰原哀立绘 + 情绪光环 / 漂浮特效叠加。

立绘来自画师 @微笑薯饼人 的微博（Q 版灰原哀系列，safebooru post #6509027），
仅用于学习演示。文件：assets/avatar.jpg（480x480）。

表情联动通过外围元素实现：光环颜色随心情冷暖变化、心动/开心飘爱心、
受伤/警惕落汗滴并整体去饱和、呼吸浮动。立绘白底经 mix-blend-mode:multiply
融入光环背景。

Gradio 的 gr.HTML 会清洗内联 <style>/<svg>，因此整个组合封装成 SVG 后
base64 为 <img> 数据 URI 输出（img 中的 SVG 动画照常运行）。
"""

import base64
from pathlib import Path

_AVATAR = Path(__file__).parent / "assets" / "avatar.jpg"
_B64 = None


def _img_b64():
    """立绘 base64（启动后缓存，约 70KB 文本）。"""
    global _B64
    if _B64 is None:
        _B64 = base64.b64encode(_AVATAR.read_bytes()).decode("ascii")
    return _B64


_CSS = """
.ha-aura{animation:haAura 4s ease-in-out infinite}
.ha-breathe{animation:haBreathe 3.6s ease-in-out infinite}
.ha-float{animation:haFloat 3s ease-in-out infinite;opacity:0}
.ha-drop{animation:haDrop 2.6s ease-in infinite;opacity:0}
@keyframes haAura{0%,100%{opacity:.4}50%{opacity:.62}}
@keyframes haBreathe{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}
@keyframes haFloat{0%{transform:translateY(0);opacity:0}25%{opacity:.9}100%{transform:translateY(-16px);opacity:0}}
@keyframes haDrop{0%{transform:translateY(0);opacity:0}20%{opacity:.9}80%{opacity:.9}100%{transform:translateY(10px);opacity:0}}
"""

_HEART = ('<path d="M 0 3 C -3 -1 -7 1 -4 5 L 0 8 L 4 5 C 7 1 3 -1 0 3 Z" '
          'fill="#f291a8" transform="translate({x},{y}) scale({s})"/>')
_DROP = '<path d="M 0 0 Q 6 11 0 17 Q -6 11 0 0 Z" fill="#a9c6e8" transform="translate({x},{y})"/>'


def _lerp(a, b, t):
    return round(a + (b - a) * t)


def _aura_color(mood):
    """心情 -100~100 映射到 冷蓝灰 → 暖桃色。"""
    t = max(0.0, min(1.0, (mood + 40) / 140))
    cool, warm = (158, 180, 209), (250, 205, 188)
    r, g, b = (_lerp(cool[i], warm[i], t) for i in range(3))
    return f"#{r:02x}{g:02x}{b:02x}"


def _expression(state, fav_d, mood_d):
    if mood_d <= -6 or fav_d <= -2:
        return "alert"    # 被冒犯：警惕
    if mood_d <= -3:
        return "hurt"     # 受伤低落
    if state.mood >= 8 or mood_d >= 5:
        return "happy"    # 真开心
    if fav_d >= 2:
        return "shy"      # 心动但别扭
    if state.favorability >= 60:
        return "soft"     # 高好感后常态变柔
    return "cold"         # 默认冷淡


def _filter(expr):
    """立绘滤镜：开心提饱和，受伤/警惕去饱和。返回 (values, 编号)。"""
    if expr in ("hurt", "alert"):
        return "0.4", "haDesat"
    if expr in ("happy", "soft", "shy"):
        return "1.25", "haSat"
    return "1", "haNone"


def _extras(expr):
    """漂浮特效：开心/害羞飘爱心，受伤/警惕落汗滴。"""
    if expr == "happy":
        return (f'<g class="ha-float">{_HEART.format(x=46, y=84, s=1.2)}</g>'
                f'<g class="ha-float" style="animation-delay:.9s">'
                f'{_HEART.format(x=188, y=74, s=1.0)}</g>')
    if expr == "shy":
        return f'<g class="ha-float">{_HEART.format(x=190, y=86, s=0.9)}</g>'
    if expr in ("hurt", "alert"):
        return f'<g class="ha-drop">{_DROP.format(x=188, y=94)}</g>'
    return ""


def render_avatar(state, fav_delta=0, mood_delta=0):
    """根据当前情绪状态渲染数字人 HTML（SVG 以 data URI 形式内嵌，规避清洗）。"""
    expr = _expression(state, fav_delta, mood_delta)
    aura = _aura_color(state.mood)
    values, fid = _filter(expr)
    filt = f' filter="url(#{fid})"' if fid != "haNone" else ""
    svg = f"""<svg viewBox="0 0 240 240" width="210" height="210" xmlns="http://www.w3.org/2000/svg">
<style>{_CSS}</style>
<defs>
  <filter id="haSat"><feColorMatrix type="saturate" values="1.25"/></filter>
  <filter id="haDesat"><feColorMatrix type="saturate" values="0.4"/></filter>
</defs>
<circle class="ha-aura" cx="120" cy="120" r="116" fill="{aura}"/>
<g class="ha-breathe">
  <image href="data:image/jpeg;base64,{_img_b64()}" x="8" y="8" width="224" height="224"
         style="mix-blend-mode:multiply"{filt}/>
  {_extras(expr)}
</g>
</svg>"""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return (f'<div style="display:flex;justify-content:center;padding:4px 0 0">'
            f'<img alt="avatar" src="data:image/svg+xml;base64,{b64}" '
            f'style="width:210px;height:210px"/></div>')
