"""SVG 活体数字人：随情绪状态实时变化表情与氛围的原创 Q 版形象。

纯代码绘制，无外部资源依赖；眨眼、呼吸、漂浮物均为 CSS 动画。
表情由情绪状态机驱动：冷淡 / 柔和 / 开心 / 害羞 / 警惕 / 受伤。

Gradio 的 gr.HTML 会清洗内联 <svg>/<style>，因此把样式内嵌进 SVG 本体，
整体 base64 后以 <img> 数据 URI 输出（img 中的 SVG 动画照常运行）。
"""

import base64

_HAIR = "#c69a72"      # 浅茶棕
_HAIR_DARK = "#a87e58"
_SKIN = "#ffe9de"
_IRIS = "#5f7fa8"      # 蓝灰
_BROW = "#7a563c"
_MOUTH = "#b06a5e"
_BLUSH = "#f2a0a0"

_CSS = """
.ha-aura{animation:haAura 4s ease-in-out infinite}
.ha-breathe{animation:haBreathe 3.6s ease-in-out infinite}
.ha-eyes{animation:haBlink 4.4s infinite;transform-box:fill-box;transform-origin:center}
.ha-float{animation:haFloat 3s ease-in-out infinite;opacity:0}
.ha-drop{animation:haDrop 2.6s ease-in infinite;opacity:0}
@keyframes haAura{0%,100%{opacity:.4}50%{opacity:.62}}
@keyframes haBreathe{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}
@keyframes haBlink{0%,93%,100%{transform:scaleY(1)}96%{transform:scaleY(.07)}}
@keyframes haFloat{0%{transform:translateY(0);opacity:0}25%{opacity:.9}100%{transform:translateY(-16px);opacity:0}}
@keyframes haDrop{0%{transform:translateY(0);opacity:0}20%{opacity:.9}80%{opacity:.9}100%{transform:translateY(10px);opacity:0}}
"""


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
        return "alert"    # 被冒犯：冷脸警惕
    if mood_d <= -3:
        return "hurt"     # 受伤低落
    if state.mood >= 8 or mood_d >= 5:
        return "happy"    # 真开心
    if fav_d >= 2:
        return "shy"      # 心动但别扭
    if state.favorability >= 60:
        return "soft"     # 高好感后常态变柔
    return "cold"         # 默认冷淡


def _brows(expr):
    if expr == "alert":
        return ('<path d="M 89 121 L 108 127"/><path d="M 131 127 L 151 121"/>')
    if expr == "hurt":
        return ('<path d="M 89 127 L 108 122"/><path d="M 131 122 L 151 127"/>')
    if expr in ("happy", "soft", "shy"):
        return ('<path d="M 89 122 Q 98 120 107 122"/><path d="M 133 122 Q 142 120 151 122"/>')
    return '<path d="M 88 123 L 108 122"/><path d="M 132 122 L 152 123"/>'


def _open_eye(cx, lid, glance=0):
    """睁开的眼睛。lid 越大眼睑垂得越低（越冷淡），glance 为瞳孔侧移（害羞瞥开）。"""
    ix = cx + glance
    return (
        f'<ellipse cx="{cx}" cy="140" rx="7.5" ry="8.5" fill="#ffffff"/>'
        f'<ellipse cx="{ix}" cy="141" rx="4.6" ry="5.4" fill="{_IRIS}"/>'
        f'<circle cx="{ix}" cy="141" r="2.4" fill="#28303c"/>'
        f'<circle cx="{ix - 1.6}" cy="139.2" r="1.4" fill="#ffffff"/>'
        f'<path d="M {cx - 8.6} 131.5 Q {cx} 128 {cx + 8.6} 131.5 L {cx + 8.6} {lid} '
        f'Q {cx} {lid - 3.5} {cx - 8.6} {lid} Z" fill="{_SKIN}"/>'
        f'<path d="M {cx - 8} 132 Q {cx} 128.6 {cx + 8} 132" stroke="#3a2f2c" '
        f'stroke-width="2.4" fill="none" stroke-linecap="round"/>'
    )


def _eyes(expr):
    if expr == "happy":  # 笑弯眼
        return (
            '<path d="M 91 140 Q 99 132 107 140" stroke="#3a2f2c" stroke-width="3" '
            'fill="none" stroke-linecap="round"/>'
            '<path d="M 133 140 Q 141 132 149 140" stroke="#3a2f2c" stroke-width="3" '
            'fill="none" stroke-linecap="round"/>')
    lid = {"cold": 139.5, "alert": 140.5, "hurt": 138.5, "shy": 138, "soft": 136.5}.get(expr, 138)
    glance = 2.6 if expr == "shy" else 0
    return f'<g class="ha-eyes">{_open_eye(99, lid, glance)}{_open_eye(141, lid, glance)}</g>'


def _mouth(expr):
    if expr == "happy":
        return '<path d="M 110 160 Q 120 172 130 160" stroke-width="2.8"/>'
    if expr == "soft":
        return '<path d="M 112 161 Q 120 167 128 161" stroke-width="2.6"/>'
    if expr == "shy":
        return '<path d="M 115 164 Q 120 166.5 125 164" stroke-width="2.4"/>'
    if expr == "hurt":
        return '<path d="M 113 166 Q 120 161 127 166" stroke-width="2.6"/>'
    if expr == "alert":
        return '<path d="M 114 164 L 126 164" stroke-width="2.6"/>'
    return '<path d="M 112 164 L 128 164" stroke-width="2.6"/>'


def _blush(expr):
    opacity = {"soft": 0.35, "happy": 0.6, "shy": 0.85}.get(expr)
    if not opacity:
        return ""
    return (f'<ellipse cx="88" cy="153" rx="7" ry="3.6" fill="{_BLUSH}" opacity="{opacity}"/>'
            f'<ellipse cx="152" cy="153" rx="7" ry="3.6" fill="{_BLUSH}" opacity="{opacity}"/>')


def _extras(expr):
    """表情附加物：开心/害羞飘爱心，受伤落汗滴。"""
    heart = ('<path d="M 0 3 C -3 -1 -7 1 -4 5 L 0 8 L 4 5 C 7 1 3 -1 0 3 Z" '
             'fill="#f291a8" transform="translate({x},{y}) scale({s})"/>')
    if expr == "happy":
        return ('<g class="ha-float">' + heart.format(x=66, y=100, s=1.1) + '</g>'
                '<g class="ha-float" style="animation-delay:.9s">'
                + heart.format(x=178, y=92, s=0.9) + '</g>')
    if expr == "shy":
        return ('<g class="ha-float">' + heart.format(x=174, y=104, s=0.85) + '</g>')
    if expr == "hurt":
        return ('<g class="ha-drop"><path d="M 172 106 Q 178 117 172 123 Q 166 117 172 106 Z" '
                'fill="#a9c6e8"/></g>')
    return ""


def render_avatar(state, fav_delta=0, mood_delta=0):
    """根据当前情绪状态渲染数字人 HTML（SVG 以 data URI 形式内嵌，规避清洗）。"""
    expr = _expression(state, fav_delta, mood_delta)
    aura = _aura_color(state.mood)
    svg = f"""<svg viewBox="0 0 240 270" width="210" height="236" xmlns="http://www.w3.org/2000/svg">
<style>{_CSS}</style>
  <circle class="ha-aura" cx="120" cy="138" r="100" fill="{aura}" style="transform-origin:120px 138px"/>
  <g class="ha-breathe">
    <!-- 后发 -->
    <path d="M 60 150 Q 52 72 120 66 Q 188 72 180 150 Q 185 178 168 192 Q 120 204 72 192 Q 55 178 60 150 Z"
          fill="{_HAIR_DARK}"/>
    <!-- 身体 -->
    <path d="M 88 200 Q 120 190 152 200 L 158 246 Q 120 254 82 246 Z" fill="#71839e"/>
    <path d="M 106 196 L 120 208 L 134 196 L 134 190 L 106 190 Z" fill="#f4f6fa"/>
    <!-- 手里的书 -->
    <g transform="rotate(-7 152 222)">
      <rect x="138" y="210" width="30" height="22" rx="4" fill="#96585a"/>
      <rect x="142" y="214" width="22" height="14" rx="2" fill="#e8ded2"/>
    </g>
    <!-- 耳朵 -->
    <ellipse cx="70" cy="140" rx="7" ry="9" fill="{_SKIN}"/>
    <ellipse cx="170" cy="140" rx="7" ry="9" fill="{_SKIN}"/>
    <!-- 脸 -->
    <ellipse cx="120" cy="136" rx="50" ry="46" fill="{_SKIN}"/>
    <!-- 前发/刘海 -->
    <path d="M 70 134 Q 64 84 120 78 Q 176 84 170 134 Q 168 112 156 104 Q 159 124 148 130
             Q 150 108 138 100 Q 138 120 126 126 Q 128 104 116 98 Q 112 118 100 124
             Q 104 106 92 102 Q 84 116 84 132 Q 76 130 70 134 Z" fill="{_HAIR}"/>
    <path d="M 74 118 Q 68 150 78 170 Q 86 150 84 126 Z" fill="{_HAIR}"/>
    <path d="M 166 118 Q 172 150 162 170 Q 154 150 156 126 Z" fill="{_HAIR}"/>
    <path d="M 120 76 Q 127 60 140 63 Q 128 68 126 79 Z" fill="{_HAIR}"/>
    <!-- 眉毛 / 眼睛 / 腮红 / 嘴 -->
    <g stroke="{_BROW}" stroke-width="3" stroke-linecap="round" fill="none">{_brows(expr)}</g>
    {_eyes(expr)}
    {_blush(expr)}
    <g stroke="{_MOUTH}" stroke-linecap="round" fill="none">{_mouth(expr)}</g>
    {_extras(expr)}
  </g>
</svg>"""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return (f'<div style="display:flex;justify-content:center;padding:4px 0 0">'
            f'<img alt="avatar" src="data:image/svg+xml;base64,{b64}" '
            f'style="width:210px;height:236px"/></div>')
