"""SVG 活体数字人：随情绪状态实时变化表情与氛围的灰原哀 Q 版形象。

造型取自原作标志特征：茶色短卷发（发尾外翘）、蓝色大眼、
帝丹小学制服（藏青西装 + 红领结）、手里永远有一本书。

纯代码绘制，无外部资源依赖；眨眼、呼吸、漂浮物均为 CSS 动画。
表情由情绪状态机驱动：冷淡 / 柔和 / 开心 / 害羞 / 警惕 / 受伤。

Gradio 的 gr.HTML 会清洗内联 <svg>/<style>，因此把样式内嵌进 SVG 本体，
整体 base64 后以 <img> 数据 URI 输出（img 中的 SVG 动画照常运行）。
"""

import base64

_HAIR = "#bd8763"      # 茶棕（原作标志发色）
_HAIR_DARK = "#99684a"
_SKIN = "#ffe9de"
_IRIS = "#4a78c0"      # 动漫蓝
_LASH = "#2c2a33"
_BROW = "#7a563c"
_MOUTH = "#b06a5e"
_BLUSH = "#f2a0a0"
_NAVY = "#3c4c72"      # 帝丹小学制服
_RIBBON = "#d13b3b"    # 红领结

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
    """睁开的动漫大眼。lid 越大眼睑垂得越低（越冷淡），glance 为瞳孔侧移（害羞瞥开）。"""
    ix = cx + glance
    return (
        f'<ellipse cx="{cx}" cy="142" rx="8.6" ry="9.8" fill="#ffffff"/>'
        f'<ellipse cx="{ix}" cy="143" rx="5.2" ry="6.2" fill="{_IRIS}"/>'
        f'<circle cx="{ix}" cy="143" r="2.6" fill="#23202e"/>'
        f'<circle cx="{ix - 1.8}" cy="140.6" r="1.7" fill="#ffffff"/>'
        f'<circle cx="{ix + 1.7}" cy="145.8" r="0.9" fill="#ffffff" opacity="0.85"/>'
        f'<path d="M {cx - 9.4} 133.5 Q {cx} 129.8 {cx + 9.4} 133.5 L {cx + 9.4} {lid} '
        f'Q {cx} {lid - 3.8} {cx - 9.4} {lid} Z" fill="{_SKIN}"/>'
        f'<path d="M {cx - 8.8} 134 Q {cx} 130.4 {cx + 8.8} 134" stroke="{_LASH}" '
        f'stroke-width="2.6" fill="none" stroke-linecap="round"/>'
        f'<path d="M {cx + 8.4} 133.6 L {cx + 11} 134.6" stroke="{_LASH}" '
        f'stroke-width="2" fill="none" stroke-linecap="round"/>'
    )


def _eyes(expr):
    if expr == "happy":  # 笑弯眼
        return (
            '<path d="M 90.5 142 Q 99 133.5 107.5 142" stroke="#2c2a33" stroke-width="3" '
            'fill="none" stroke-linecap="round"/>'
            '<path d="M 132.5 142 Q 141 133.5 149.5 142" stroke="#2c2a33" stroke-width="3" '
            'fill="none" stroke-linecap="round"/>')
    lid = {"cold": 141.5, "alert": 142.5, "hurt": 140.5, "shy": 140, "soft": 138.5}.get(expr, 140)
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
    <!-- 后发：波波头 + 发尾外翘（她的标志） -->
    <path d="M 56 150 Q 48 64 120 58 Q 192 64 184 150 Q 186 170 172 178
             Q 150 192 120 192 Q 90 192 68 178 Q 54 170 56 150 Z" fill="{_HAIR_DARK}"/>
    <path d="M 178 140 Q 196 142 202 158 Q 190 156 180 152 Z" fill="{_HAIR_DARK}"/>
    <path d="M 174 164 Q 192 170 196 188 Q 184 182 172 176 Z" fill="{_HAIR_DARK}"/>
    <path d="M 62 140 Q 44 142 38 158 Q 50 156 60 152 Z" fill="{_HAIR_DARK}"/>
    <path d="M 66 164 Q 48 170 44 188 Q 56 182 68 176 Z" fill="{_HAIR_DARK}"/>
    <!-- 帝丹小学制服：藏青西装 + 白衬衫 + 红领结 -->
    <path d="M 86 202 Q 120 190 154 202 L 160 248 Q 120 256 80 248 Z" fill="{_NAVY}"/>
    <path d="M 104 190 L 136 190 L 136 196 L 120 210 L 104 196 Z" fill="#f6f8fb"/>
    <g fill="{_RIBBON}">
      <path d="M 120 202 L 109 196 L 109 208 Z"/>
      <path d="M 120 202 L 131 196 L 131 208 Z"/>
      <circle cx="120" cy="202" r="2.6"/>
    </g>
    <!-- 手里的书 -->
    <g transform="rotate(-7 152 224)">
      <rect x="138" y="212" width="30" height="22" rx="4" fill="#96585a"/>
      <rect x="142" y="216" width="22" height="14" rx="2" fill="#e8ded2"/>
    </g>
    <!-- 耳朵 -->
    <ellipse cx="70" cy="140" rx="7" ry="9" fill="{_SKIN}"/>
    <ellipse cx="170" cy="140" rx="7" ry="9" fill="{_SKIN}"/>
    <!-- 脸 -->
    <ellipse cx="120" cy="136" rx="50" ry="46" fill="{_SKIN}"/>
    <!-- 前发/刘海：侧分碎发 -->
    <path d="M 70 134 Q 60 80 120 74 Q 180 80 170 134 Q 168 114 158 104 Q 161 126 150 132
             Q 151 110 141 100 Q 141 122 130 128 Q 131 104 120 98 Q 114 120 102 126
             Q 105 106 94 102 Q 84 114 83 132 Q 76 130 70 134 Z" fill="{_HAIR}"/>
    <path d="M 74 116 Q 66 150 78 176 Q 88 152 84 124 Z" fill="{_HAIR}"/>
    <path d="M 166 116 Q 174 150 162 176 Q 152 152 156 124 Z" fill="{_HAIR}"/>
    <path d="M 118 74 Q 126 58 140 62 Q 127 67 125 78 Z" fill="{_HAIR}"/>
    <!-- 发丝纹理 -->
    <g stroke="{_HAIR_DARK}" stroke-width="1.6" fill="none" opacity="0.55" stroke-linecap="round">
      <path d="M 86 86 Q 78 108 82 130"/>
      <path d="M 154 86 Q 162 108 158 130"/>
    </g>
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
