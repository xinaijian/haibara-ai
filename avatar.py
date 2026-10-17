"""SVG 活体数字人：随情绪状态实时变化表情与氛围的灰原哀 Q 版形象。

造型参照官方风 Q 版图重绘：巨大头身比、茶棕蓬松短发（发尾外翘、
刘海中垂一缕）、蓝色大眼（粗黑上眼线、外眼角微垂）、白大褂 + 红衬衫、
背手站姿。纯代码绘制，无外部资源依赖；眨眼、呼吸、漂浮物均为 CSS 动画。
表情由情绪状态机驱动：冷淡 / 柔和 / 开心 / 害羞 / 警惕 / 受伤。

Gradio 的 gr.HTML 会清洗内联 <svg>/<style>，因此把样式内嵌进 SVG 本体，
整体 base64 后以 <img> 数据 URI 输出（img 中的 SVG 动画照常运行）。
"""

import base64

_HAIR = "#b0875f"      # 茶棕
_HAIR_DARK = "#8a6547"
_HAIR_SHEEN = "#c99a72"
_SKIN = "#ffeedf"
_IRIS = "#4f8fc7"      # 动漫蓝
_LASH = "#1f1b24"
_BROW = "#5a4436"
_MOUTH = "#a35a50"
_BLUSH = "#f2a0a0"
_COAT = "#f7f5f0"      # 白大褂
_SHIRT = "#a83838"     # 红衬衫
_SHORTS = "#6b4f3f"
_SHOE = "#8a3a3a"
_LINE = "#2c2833"      # 服装描边

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
        return ('<path d="M 78 112 L 92 116"/><path d="M 148 116 L 162 112"/>')
    if expr == "hurt":
        return ('<path d="M 78 116 L 92 113"/><path d="M 148 113 L 162 116"/>')
    if expr in ("happy", "soft", "shy"):
        return ('<path d="M 78 113 Q 85 111 92 113"/><path d="M 148 113 Q 155 111 162 113"/>')
    return '<path d="M 78 114 L 92 112"/><path d="M 148 112 L 162 114"/>'


def _open_eye(cx, lid, glance, side):
    """睁开的动漫大眼：粗黑眼眶 + 蓝瞳。lid 越大眼睑垂得越低（越冷淡），
    glance 为瞳孔侧移（害羞瞥开），side 决定外眼角下垂小睫毛的方向。"""
    ix = cx + glance
    return (
        f'<ellipse cx="{cx}" cy="138" rx="15.5" ry="13.5" fill="{_LASH}"/>'
        f'<ellipse cx="{cx}" cy="138.5" rx="13.8" ry="12" fill="#ffffff"/>'
        f'<ellipse cx="{ix}" cy="140" rx="9" ry="9" fill="{_IRIS}"/>'
        f'<ellipse cx="{ix}" cy="140" rx="3.6" ry="4.2" fill="#14121c"/>'
        f'<circle cx="{ix - 3.5}" cy="135.5" r="2.8" fill="#ffffff"/>'
        f'<circle cx="{ix + 3.5}" cy="144.5" r="1.4" fill="#ffffff" opacity="0.9"/>'
        # 上眼睑遮罩（肤色，决定冷淡程度）+ 下缘睫毛线
        f'<path d="M {cx - 15.5} 124.5 Q {cx} 120 {cx + 15.5} 124.5 L {cx + 15.5} {lid} '
        f'Q {cx} {lid - 4} {cx - 15.5} {lid} Z" fill="{_SKIN}"/>'
        f'<path d="M {cx - 15.5} {lid} Q {cx} {lid - 4} {cx + 15.5} {lid}" '
        f'stroke="{_LASH}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
        # 外眼角微垂（她的标志倦态）
        f'<path d="M {cx + side * 14} 129.5 L {cx + side * 18} 133" stroke="{_LASH}" '
        f'stroke-width="3" fill="none" stroke-linecap="round"/>'
    )


def _eyes(expr):
    if expr == "happy":  # 笑弯眼
        return (
            f'<path d="M 75 140 Q 88 128 101 140" stroke="{_LASH}" stroke-width="4" '
            f'fill="none" stroke-linecap="round"/>'
            f'<path d="M 139 140 Q 152 128 165 140" stroke="{_LASH}" stroke-width="4" '
            f'fill="none" stroke-linecap="round"/>')
    lid = {"cold": 136.5, "alert": 138.5, "hurt": 135.5, "shy": 135, "soft": 131}.get(expr, 134)
    glance = 2.6 if expr == "shy" else 0
    return (f'<g class="ha-eyes">{_open_eye(88, lid, glance, -1)}'
            f'{_open_eye(152, lid, glance, 1)}</g>')


def _mouth(expr):
    if expr == "happy":
        return '<path d="M 111 165 Q 120 175 129 165" stroke-width="3"/>'
    if expr == "soft":
        return '<path d="M 113 166 Q 120 171 127 166" stroke-width="2.8"/>'
    if expr == "shy":
        return '<path d="M 115 167 Q 120 169.5 125 167" stroke-width="2.6"/>'
    if expr == "hurt":
        return '<path d="M 112 169 Q 120 164 128 169" stroke-width="2.8"/>'
    if expr == "alert":
        return '<path d="M 113 167.5 L 127 167.5" stroke-width="2.8"/>'
    return '<path d="M 112 167 L 128 167" stroke-width="2.8"/>'


def _blush(expr):
    opacity = {"soft": 0.35, "happy": 0.6, "shy": 0.85}.get(expr)
    if not opacity:
        return ""
    return (f'<ellipse cx="72" cy="154" rx="9" ry="4.5" fill="{_BLUSH}" opacity="{opacity}"/>'
            f'<ellipse cx="168" cy="154" rx="9" ry="4.5" fill="{_BLUSH}" opacity="{opacity}"/>')


def _extras(expr):
    """表情附加物：开心/害羞飘爱心，受伤落汗滴。"""
    heart = ('<path d="M 0 3 C -3 -1 -7 1 -4 5 L 0 8 L 4 5 C 7 1 3 -1 0 3 Z" '
             'fill="#f291a8" transform="translate({x},{y}) scale({s})"/>')
    if expr == "happy":
        return ('<g class="ha-float">' + heart.format(x=48, y=88, s=1.2) + '</g>'
                '<g class="ha-float" style="animation-delay:.9s">'
                + heart.format(x=194, y=80, s=1.0) + '</g>')
    if expr == "shy":
        return ('<g class="ha-float">' + heart.format(x=192, y=92, s=0.9) + '</g>')
    if expr == "hurt":
        return ('<g class="ha-drop"><path d="M 200 100 Q 206 111 200 117 Q 194 111 200 100 Z" '
                'fill="#a9c6e8"/></g>')
    return ""


def render_avatar(state, fav_delta=0, mood_delta=0):
    """根据当前情绪状态渲染数字人 HTML（SVG 以 data URI 形式内嵌，规避清洗）。"""
    expr = _expression(state, fav_delta, mood_delta)
    aura = _aura_color(state.mood)
    svg = f"""<svg viewBox="0 0 240 270" width="210" height="236" xmlns="http://www.w3.org/2000/svg">
<style>{_CSS}</style>
  <circle class="ha-aura" cx="120" cy="140" r="106" fill="{aura}" style="transform-origin:120px 140px"/>
  <g class="ha-breathe">
    <!-- 后发：蓬松巨帽 + 发尾外翘 -->
    <path d="M 44 148 Q 30 128 40 108 Q 30 84 46 66 Q 44 44 68 40 Q 66 22 96 24
             Q 108 10 132 22 Q 158 12 168 32 Q 192 30 194 54 Q 208 62 200 84
             Q 210 104 200 124 Q 208 142 196 152 Q 170 168 120 170 Q 70 168 44 148 Z"
          fill="{_HAIR}"/>
    <path d="M 52 146 Q 34 150 30 168 Q 44 164 54 158 Z" fill="{_HAIR}"/>
    <path d="M 58 160 Q 44 168 44 184 Q 56 176 64 170 Z" fill="{_HAIR}"/>
    <path d="M 188 146 Q 206 150 210 168 Q 196 164 186 158 Z" fill="{_HAIR}"/>
    <path d="M 182 160 Q 196 168 196 184 Q 184 176 176 170 Z" fill="{_HAIR}"/>
    <!-- 白大褂 + 红衬衫（背手站姿） -->
    <path d="M 100 192 Q 120 186 140 192 L 142 224 Q 120 230 98 224 Z" fill="{_SHIRT}"/>
    <path d="M 98 192 Q 82 198 80 218 L 82 244 Q 94 250 104 244 L 106 214 Q 104 200 102 194 Z"
          fill="{_COAT}" stroke="{_LINE}" stroke-width="2.5"/>
    <path d="M 142 192 Q 158 198 160 218 L 158 244 Q 146 250 136 244 L 134 214 Q 136 200 138 194 Z"
          fill="{_COAT}" stroke="{_LINE}" stroke-width="2.5"/>
    <path d="M 106 190 L 120 200 L 134 190 L 134 186 L 106 186 Z" fill="{_COAT}"/>
    <rect x="86" y="224" width="12" height="10" rx="2" fill="none" stroke="{_LINE}" stroke-width="2"/>
    <path d="M 104 224 L 136 224 L 136 237 Q 128 239 124 235 L 120 231 L 116 235 Q 112 239 104 237 Z"
          fill="{_SHORTS}"/>
    <rect x="106" y="238" width="8" height="14" rx="3" fill="{_SKIN}"/>
    <rect x="126" y="238" width="8" height="14" rx="3" fill="{_SKIN}"/>
    <ellipse cx="109" cy="254" rx="11" ry="6" fill="{_SHOE}"/>
    <ellipse cx="131" cy="254" rx="11" ry="6" fill="{_SHOE}"/>
    <!-- 耳朵 -->
    <ellipse cx="56" cy="132" rx="7" ry="9" fill="{_SKIN}"/>
    <ellipse cx="184" cy="132" rx="7" ry="9" fill="{_SKIN}"/>
    <!-- 脸 -->
    <ellipse cx="120" cy="132" rx="62" ry="52" fill="{_SKIN}"/>
    <!-- 刘海：侧分碎发 + 中垂一缕（她的标志） -->
    <path d="M 64 128 Q 56 84 92 70 Q 118 56 150 64 Q 178 70 180 100 Q 182 116 172 126
             Q 168 108 158 100 Q 160 118 148 124 Q 148 104 138 98 Q 138 116 128 122
             Q 124 104 116 100 Q 110 118 100 124 Q 100 106 92 104 Q 84 118 76 126
             Q 70 120 64 128 Z" fill="{_HAIR}"/>
    <path d="M 118 96 Q 115 118 120 132 Q 125 118 124 98 Z" fill="{_HAIR}"/>
    <path d="M 64 110 Q 56 140 66 164 Q 74 166 74 156 Q 66 136 74 118 Z" fill="{_HAIR}"/>
    <path d="M 176 110 Q 184 140 174 164 Q 166 166 166 156 Q 174 136 166 118 Z" fill="{_HAIR}"/>
    <!-- 发丝光泽 -->
    <path d="M 78 60 Q 96 44 122 42" stroke="{_HAIR_SHEEN}" stroke-width="5"
          fill="none" opacity="0.5" stroke-linecap="round"/>
    <!-- 眉毛 / 眼睛 / 鼻子 / 腮红 / 嘴 -->
    <g stroke="{_BROW}" stroke-width="3" stroke-linecap="round" fill="none">{_brows(expr)}</g>
    {_eyes(expr)}
    <circle cx="120" cy="157" r="1.2" fill="#d9a58c"/>
    {_blush(expr)}
    <g stroke="{_MOUTH}" stroke-linecap="round" fill="none">{_mouth(expr)}</g>
    {_extras(expr)}
  </g>
</svg>"""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return (f'<div style="display:flex;justify-content:center;padding:4px 0 0">'
            f'<img alt="avatar" src="data:image/svg+xml;base64,{b64}" '
            f'style="width:210px;height:236px"/></div>')
