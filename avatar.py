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
        return ('<path d="M 76 115.5 L 92 120"/><path d="M 148 120 L 164 115.5"/>')
    if expr == "hurt":
        return ('<path d="M 76 120.5 L 92 116.5"/><path d="M 148 116.5 L 164 120.5"/>')
    if expr in ("happy", "soft", "shy"):
        return ('<path d="M 76 117.5 Q 84 115.5 92 117"/>'
                '<path d="M 148 117 Q 156 115.5 164 117.5"/>')
    return '<path d="M 76 118 L 92 117"/><path d="M 148 117 L 164 118"/>'


def _open_eye(cx, lid, glance, side):
    """动漫大眼：蓝瞳全露 + 粗黑上眼线（外端低、内端高 → 倦态下垂）。
    lid 为眼线外端 y：越大越慵懒，越小睁得越开。side=±1 指向外侧。"""
    ix = cx + glance
    return (
        # 眼眶（深色底） + 眼白
        f'<ellipse cx="{cx}" cy="141.5" rx="16" ry="14.4" fill="{_LASH}"/>'
        f'<ellipse cx="{cx}" cy="141.5" rx="14.9" ry="13.4" fill="#ffffff"/>'
        # 虹膜：亮蓝主体 + 深蓝上半环 + 底部反光 + 瞳孔 + 双高光
        f'<circle cx="{ix}" cy="142.5" r="10.4" fill="{_IRIS}"/>'
        f'<path d="M {ix - 10.4} 142.5 A 10.4 10.4 0 0 1 {ix + 10.4} 142.5 Z" fill="#2e5c99"/>'
        f'<ellipse cx="{ix}" cy="149" rx="5.6" ry="3" fill="#7db4e6"/>'
        f'<circle cx="{ix}" cy="142.5" r="4.2" fill="#151223"/>'
        f'<circle cx="{ix - 3.4}" cy="138.8" r="2.8" fill="#ffffff"/>'
        f'<circle cx="{ix + 3.8}" cy="146.2" r="1.5" fill="#ffffff" opacity="0.9"/>'
        # 上眼睑遮罩（肤色）：外端下垂、内端高
        f'<path d="M {cx - side * 17.5} 125.5 L {cx + side * 18.5} 122.5 '
        f'L {cx + side * 18.5} {lid + 3} Q {cx} {lid - 1.5} {cx - side * 17.5} 130.5 Z" '
        f'fill="{_SKIN}"/>'
        # 粗黑上眼线沿眼睑下缘
        f'<path d="M {cx + side * 18.5} {lid + 3} Q {cx} {lid - 1.5} {cx - side * 17.5} 130.5" '
        f'stroke="{_LASH}" stroke-width="4" fill="none" stroke-linecap="round"/>'
        # 外眼角下垂小睫毛（她的标志倦态）
        f'<path d="M {cx + side * 17} {lid + 2} L {cx + side * 22.5} {lid + 6.5}" '
        f'stroke="{_LASH}" stroke-width="3.2" fill="none" stroke-linecap="round"/>'
        # 下睫毛（外半段，轻）
        f'<path d="M {cx + side * 7} 155.8 Q {cx + side * 13} 155.2 {cx + side * 16.5} 151.8" '
        f'stroke="{_LASH}" stroke-width="2" fill="none" stroke-linecap="round" opacity="0.85"/>'
    )


def _eyes(expr):
    if expr == "happy":  # 笑弯眼
        return (
            f'<path d="M 74 142 Q 88 128 102 142" stroke="{_LASH}" stroke-width="4" '
            f'fill="none" stroke-linecap="round"/>'
            f'<path d="M 138 142 Q 152 128 166 142" stroke="{_LASH}" stroke-width="4" '
            f'fill="none" stroke-linecap="round"/>')
    lid = {"cold": 132.5, "alert": 127, "hurt": 135.5, "shy": 132, "soft": 131}.get(expr, 132.5)
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
    return (f'<ellipse cx="80" cy="155" rx="8" ry="4" fill="{_BLUSH}" opacity="{opacity}"/>'
            f'<ellipse cx="160" cy="155" rx="8" ry="4" fill="{_BLUSH}" opacity="{opacity}"/>')


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
    <!-- 后发：顺滑圆穹顶 -->
    <path d="M 54 142 Q 40 100 62 66 Q 58 30 96 22 Q 120 10 146 22 Q 184 30 180 66
             Q 202 100 188 142 Q 184 158 170 160 Q 120 170 70 160 Q 56 158 54 142 Z"
          fill="{_HAIR}"/>
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
    <!-- 脸 -->
    <ellipse cx="120" cy="132" rx="62" ry="52" fill="{_SKIN}"/>
    <!-- 侧发：沿脸颊垂落到下巴，发梢波浪外翘 -->
    <path d="M 60 92 Q 46 116 50 140 Q 53 162 44 178 Q 54 174 58 186 Q 64 178 70 187
             Q 74 172 73 156 Q 72 126 76 100 Z" fill="{_HAIR}"/>
    <path d="M 180 92 Q 194 116 190 140 Q 187 162 196 178 Q 186 174 182 186 Q 176 178 170 187
             Q 166 172 167 156 Q 168 126 164 100 Z" fill="{_HAIR}"/>
    <g stroke="{_HAIR_DARK}" stroke-width="1.8" fill="none" opacity="0.5" stroke-linecap="round">
      <path d="M 57 104 Q 51 130 53 156"/>
      <path d="M 183 104 Q 189 130 187 156"/>
    </g>
    <!-- 刘海：覆盖额头的波浪碎发（尖端朝下） -->
    <path d="M 64 112 Q 56 82 88 71 Q 120 58 152 67 Q 180 78 176 112
             Q 172 118 168 120 Q 163 110 157 104 Q 151 112 146 122
             Q 142 112 139 104 Q 135 114 132 124 Q 127 114 123 106
             Q 118 114 114 122 Q 109 112 105 104 Q 100 110 96 118
             Q 90 110 84 102 Q 78 108 72 116 Q 68 116 64 112 Z" fill="{_HAIR}"/>
    <!-- 中垂一缕（她的标志） -->
    <path d="M 118 92 Q 114 112 119 130 Q 124 114 123 94 Z" fill="{_HAIR}"/>
    <!-- 发丝光泽 + 刘海流向 -->
    <path d="M 80 52 Q 102 34 128 32" stroke="{_HAIR_SHEEN}" stroke-width="5"
          fill="none" opacity="0.5" stroke-linecap="round"/>
    <g stroke="{_HAIR_DARK}" stroke-width="1.8" fill="none" opacity="0.55" stroke-linecap="round">
      <path d="M 100 76 Q 95 92 92 108"/>
      <path d="M 144 74 Q 149 90 147 108"/>
      <path d="M 122 70 Q 120 84 121 96"/>
      <path d="M 80 88 Q 77 98 75 108"/>
      <path d="M 162 88 Q 165 98 166 108"/>
    </g>
    <!-- 眉毛 / 眼睛 / 鼻子 / 腮红 / 嘴 -->
    <g stroke="{_BROW}" stroke-width="2.6" stroke-linecap="round" fill="none">{_brows(expr)}</g>
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
