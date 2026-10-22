from playwright.sync_api import sync_playwright
PRODUTOS = [
 ("fone","🎧","#C9D6F2","#9FB6E8"),("airfryer","🍳","#F6D7C3","#EDB28F"),("garrafa","🧴","#CDEBDD","#9FD6BC"),("mochila","🎒","#F2D3DA","#E7A9B8"),
 ("relogio","⌚","#DAD3F2","#B8ABE6"),("luminaria","💡","#F8EDB8","#F0D96C"),("tenis","👟","#D3E8F2","#A5CCE2"),("urso","🧸","#F5DCC2","#E8BC8F"),
 ("batom","💄","#F6CFD9","#EE9BB3"),("panela","🥘","#E3E3E3","#C4C4C4"),("tapete","🧶","#E1EBD0","#BFD39A"),("camera","📷","#D5D9E0","#AEB6C4"),
 ("violao","🎸","#F2D9C2","#E3B58C"),("planta","🪴","#D3EBD0","#A4D29E"),("bolsa","👜","#EBD3E8","#D4A5CE"),("bike","🚲","#D0E8EE","#9CCDD9"),
 ("copo","🥤","#F5E0CB","#EBC095"),("controle","🎮","#D9D3F0","#B3A8E3"),("secador","💨","#F3D5D5","#E5A5A5"),("tv","📺","#D3DDEB","#A9BCD6"),
 ("fritadeira","🍟","#F7E4B8","#EFCB73"),("vaso","🏺","#EBD5C3","#D8AE8D"),("livro","📚","#D6E3D3","#A9C8A3"),("kit","🧰","#E6D9CC","#CFB596"),
]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg=b.new_page(viewport={"width":400,"height":400})
    for nome,em,c1,c2 in PRODUTOS:
        pg.set_content(f'<body style="margin:0;width:400px;height:400px;display:grid;place-items:center;background:radial-gradient(circle at 30% 25%,{c1},{c2});font-size:190px;font-family:\'Noto Color Emoji\',sans-serif"><span style="filter:drop-shadow(0 14px 14px rgba(0,0,0,.22))">{em}</span></body>')
        pg.screenshot(path=f"img/{nome}.jpg",type="jpeg",quality=88)
    b.close()
print(len(PRODUTOS))
