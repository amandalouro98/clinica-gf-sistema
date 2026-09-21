"""Espelho visual do Google Calendar dentro do sistema.

Grade no estilo do Google (visão de dia): uma coluna por calendário
(profissionais e salas), blocos coloridos posicionados pela duração e
linha vermelha no horário atual. Mostra SOMENTE eventos vindos do Google
(agendamentos com vínculo em GoogleEvento).

Clique em um bloco abre o pop-up de edição: o bloco aciona um botão
oculto do Streamlit na página mãe (mesma ponte da grade FullCalendar) —
navegar por URL recarregaria a página e derrubaria o login.

Versão mobile: lista do dia colorida, como o Google Calendar mobile.
"""
import html
from datetime import datetime, timedelta, timezone

BR_TZ = timezone(timedelta(hours=-3))

# Janela de exibição da grade (horas cheias)
HORA_INI = 7   # 07:00
HORA_FIM = 22  # 22:00
PX_POR_HORA = 56

# Ponte JS <-> Streamlit (mesma da grade FullCalendar)
_JS_PONTE = f"""
function docPai() {{
    try {{
        return (window.parent && window.parent !== window) ? window.parent.document : document;
    }} catch (e) {{
        return null;
    }}
}}
function textoBotao(btn) {{
    return ((btn.innerText || btn.textContent) || '').trim();
}}
function acharBotao(marcador) {{
    var doc = docPai();
    if (!doc) return null;
    var botoes = doc.querySelectorAll('button');
    for (var i = 0; i < botoes.length; i++) {{
        if (textoBotao(botoes[i]) === marcador) return botoes[i];
    }}
    return null;
}}
function acionar(marcador) {{
    var btn = acharBotao(marcador);
    if (btn) {{ btn.click(); return true; }}
    console.warn('Ponte nao encontrada para ' + marcador);
    return false;
}}
function clicouFundo(ev) {{
    var alvo = ev.currentTarget;
    var rect = alvo.getBoundingClientRect();
    if (!rect.height) return;
    var totalMin = {(HORA_FIM - HORA_INI) * 60};
    var minIni = {HORA_INI * 60};
    var maxSlot = 20 * 60;  // último horário com botão na ponte (grade de agendamento)
    var y = ev.clientY - rect.top;
    var minutos = minIni + Math.floor((y / rect.height) * totalMin / 15) * 15;
    if (minutos > maxSlot) minutos = maxSlot;
    if (minutos < minIni) minutos = minIni;
    var hh = ('0' + Math.floor(minutos / 60)).slice(-2);
    var mm = ('0' + (minutos % 60)).slice(-2);
    acionar('agx-esp-novo-' + hh + ':' + mm);
}}
"""


# Ajusta a altura do iframe ao conteúdo (a lista mobile pode ser mais alta
# que a grade; sem isso os agendamentos de baixo ficam cortados, sem rolagem)
_JS_ALTURA = """
function ajustarAltura() {
    try {
        var h = document.documentElement.scrollHeight;
        if (document.body) h = Math.max(h, document.body.scrollHeight);
        if (window.frameElement && h > 100) {
            window.frameElement.style.height = h + 'px';
        }
    } catch (e) {}
}
window.addEventListener('load', ajustarAltura);
window.addEventListener('resize', ajustarAltura);
setTimeout(ajustarAltura, 50);
setTimeout(ajustarAltura, 300);
setTimeout(ajustarAltura, 900);
"""


def altura_px_grade():
    """Altura total do iframe da grade (grade + cabeçalho)."""
    return (HORA_FIM - HORA_INI) * PX_POR_HORA + 40


def _minutos(texto, padrao=0):
    try:
        hh, mm = str(texto or "00:00").split(":")[:2]
        return int(hh) * 60 + int(mm)
    except Exception:
        return padrao


def _carregar_blocos(db, data):
    """Carrega eventos do Google do dia com cores/nomes dos calendários.

    Retorna (blocos, cores, nomes, total) onde blocos está ordenado por hora.
    """
    from models.professional import Professional
    from models.room import Room
    from models.schedule import ScheduledAppointment
    from models.google_sync import GoogleEvento

    cores = {}
    nomes = {}
    for p in db.query(Professional).all():
        if p.google_calendar_id:
            cores[p.google_calendar_id] = p.cor or "#E3A5C7"
            nomes[p.google_calendar_id] = p.nome
    for r in db.query(Room).all():
        if r.google_calendar_id:
            cores[r.google_calendar_id] = r.cor or "#E3A5C7"
            nomes[r.google_calendar_id] = r.nome

    if not cores:
        return [], cores, nomes, 0

    links = (
        db.query(GoogleEvento, ScheduledAppointment)
        .join(ScheduledAppointment, GoogleEvento.agendamento_id == ScheduledAppointment.id)
        .filter(ScheduledAppointment.data == data)
        .all()
    )

    blocos = []
    for link, ag in links:
        cal_id = link.calendar_id
        if cal_id not in cores:
            continue
        cor = cores[cal_id]
        titulo = (ag.cliente_nome or "").strip() or "(sem título)"
        if ag.procedimento:
            titulo = f"{titulo} · {ag.procedimento}"
        sub_itens = []
        if ag.sala:
            sub_itens.append(ag.sala)
        sub = " · ".join(sub_itens)

        dica = f"{ag.hora_inicio}–{ag.hora_fim} · {titulo}"
        if ag.sala:
            dica += f" · {ag.sala}"
        if getattr(ag, "pre_agendamento", False):
            dica += " · pré-agendamento"
        elif ag.confirmado:
            dica += " · confirmado"

        blocos.append({
            "ag_id": ag.id,
            "titulo": html.escape(titulo),
            "sub": html.escape(sub),
            "hora": f"{ag.hora_inicio or ''}–{ag.hora_fim or ''}",
            "prof": html.escape(nomes.get(cal_id, "")),
            "cor": cor,
            "dica": html.escape(dica),
            "ini": _minutos(ag.hora_inicio, HORA_INI * 60),
            "dur": max(20, _minutos(ag.hora_fim, _minutos(ag.hora_inicio, HORA_INI * 60) + 60) - _minutos(ag.hora_inicio, HORA_INI * 60)),
            "cal_id": cal_id,
        })

    blocos.sort(key=lambda b: (b["ini"], b["titulo"]))
    return blocos, cores, nomes, len(blocos)


def _html_grade(db, data, blocos, cores):
    """Retorna HTML interno da visão em grade (desktop)."""
    from models.professional import Professional
    from models.room import Room
    from models.google_sync import GoogleEvento

    colunas = []  # [(calendar_id, nome, cor, tipo)]
    for p in db.query(Professional).order_by(Professional.nome.asc()).all():
        if p.google_calendar_id:
            colunas.append((p.google_calendar_id, p.nome, p.cor or "#E3A5C7", "prof"))
    for r in db.query(Room).order_by(Room.nome.asc()).all():
        if r.google_calendar_id:
            colunas.append((r.google_calendar_id, r.nome, r.cor or "#E3A5C7", "sala"))
    if not colunas:
        return ""

    blocos_por_col = {c[0]: [] for c in colunas}
    for b in blocos:
        if b["cal_id"] in blocos_por_col:
            blocos_por_col[b["cal_id"]].append(b)

    # linha do horário atual
    agora = datetime.now(BR_TZ)
    linha_agora = ""
    if agora.date() == data:
        m = agora.hour * 60 + agora.minute
        total = (HORA_FIM - HORA_INI) * 60
        if HORA_INI * 60 <= m <= HORA_FIM * 60:
            top_pct = (m - HORA_INI * 60) / total * 100
            linha_agora = (
                f'<div style="position:absolute;left:0;right:0;top:{top_pct:.2f}%;'
                'height:2px;background:#d93025;z-index:5;"></div>'
            )

    altura = (HORA_FIM - HORA_INI) * PX_POR_HORA
    marcas, eixo = [], []
    for h in range(HORA_INI, HORA_FIM + 1):
        top = (h - HORA_INI) * PX_POR_HORA
        marcas.append(
            f'<div style="position:absolute;top:{top}px;left:0;width:100%;'
            'border-top:1px solid #eee;"></div>'
        )
        eixo.append(
            f'<div style="position:absolute;top:{top - 7}px;left:0;width:46px;'
            'text-align:right;font-size:11px;color:#999;padding-right:4px;'
            f'background:#fff;z-index:2;">{h:02d}:00</div>'
        )

    total = (HORA_FIM - HORA_INI) * 60
    html_cols = []
    for cal_id, nome, cor, _tipo in colunas:
        blocos_html = []
        for b in blocos_por_col.get(cal_id, []):
            top_pct = max(0.0, (b["ini"] - HORA_INI * 60) / total * 100)
            alt_pct = b["dur"] / total * 100
            blocos_html.append(
                f'<div title="{b["dica"]} — clique para editar" '
                f'onclick="event.stopPropagation();acionar(\'agx-esp-{b["ag_id"]}\')" '
                f'style="position:absolute;'
                f'top:calc({top_pct:.3f}% + 1px);height:calc({alt_pct:.3f}% - 2px);'
                f'left:2px;right:2px;background:{cor};border-radius:6px;'
                'padding:3px 5px;overflow:hidden;color:#fff;z-index:3;'
                'box-shadow:0 1px 2px rgba(0,0,0,.25);cursor:pointer;">'
                f'<div style="font-size:11px;font-weight:600;line-height:1.2;'
                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{b["titulo"]}</div>'
                f'<div style="font-size:10px;opacity:.9;">{b["hora"]}</div>'
                '</div>'
            )
        html_cols.append(
            f'<div onclick="clicouFundo(event)" '
            f'title="Clique para criar um agendamento neste horário" '
            f'style="flex:1;min-width:130px;position:relative;'
            f'border-left:1px solid #eee;cursor:copy;">{linha_agora}{"".join(blocos_html)}</div>'
        )

    cabecalhos = "".join(
        f'<div style="flex:1;min-width:130px;padding:6px 4px;text-align:center;">'
        f'<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:50%;background:{cor};margin-right:5px;"></span>'
        f'<span style="font-size:12px;font-weight:600;color:#5a4038;">{html.escape(nome)}</span>'
        f'</div>'
        for _cal, nome, cor, _t in colunas
    )

    return f"""<div class="gf-view-desktop">
<div style="border:1px solid #f0d5ce;border-radius:12px;overflow:hidden;background:#fff;">
    <div style="display:flex;border-bottom:1px solid #f0d5ce;background:#fdf6f4;">
        <div style="width:52px;flex:none;"></div>{cabecalhos}
    </div>
    <div style="overflow-x:auto;">
        <div style="display:flex;min-width:100%;">
            <div style="width:52px;flex:none;position:relative;height:{altura}px;
                background:#fff;z-index:4;border-right:1px solid #eee;">{"".join(eixo)}</div>
            <div style="flex:1;position:relative;height:{altura}px;">
                <div style="position:absolute;inset:0;z-index:1;">{"".join(marcas)}</div>
                <div style="display:flex;position:absolute;inset:0;z-index:2;">
                    {"".join(html_cols)}
                </div>
            </div>
        </div>
    </div>
</div>
</div>"""


def _html_lista(data, blocos, hoje=None):
    """Retorna HTML interno da visão em lista (mobile)."""
    if hoje is None:
        hoje = datetime.now(BR_TZ).date()

    if data == hoje:
        cabecalho = (
            f'<div style="font-size:14px;color:#d93025;font-weight:700;margin-bottom:12px;">'
            f'Hoje · {data.strftime("%d/%m/%Y")}</div>'
        )
    else:
        dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        dia_sem = dias[data.weekday()]
        cabecalho = (
            f'<div style="font-size:14px;color:#5a4038;font-weight:700;margin-bottom:12px;">'
            f'{dia_sem} · {data.strftime("%d/%m/%Y")}</div>'
        )

    if not blocos:
        lista = (
            '<div style="text-align:center;padding:48px 20px;color:#9e7575;font-size:15px;">'
            'Nenhum agendamento para este dia.</div>'
        )
    else:
        cards = []
        for b in blocos:
            # cor mais clara para o fundo e cor original na barra lateral
            cor = b["cor"]
            r = int(cor[1:3], 16)
            g = int(cor[3:5], 16)
            bb = int(cor[5:7], 16)
            bg_claro = f"rgba({r},{g},{bb},0.12)"

            sub_linhas = []
            if b["sub"]:
                sub_linhas.append(b["sub"])
            if b["prof"]:
                sub_linhas.append(b["prof"])
            sub_html = (
                f'<div style="font-size:13px;color:#5a4038;opacity:.85;line-height:1.35;margin-top:4px;">'
                f'{" · ".join(sub_linhas)}</div>'
            ) if sub_linhas else ""

            ini = (b["hora"] or "").split("–")[0] or ""

            cards.append(
                f'<div title="{b["dica"]}" '
                f'onclick="acionar(\'agx-esp-{b["ag_id"]}\')" '
                'style="display:flex;background:#fff;border-radius:10px;'
                'margin-bottom:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08);'
                'cursor:pointer;-webkit-tap-highlight-color:transparent;">'
                f'<div style="width:5px;flex:none;background:{cor};"></div>'
                f'<div style="flex:1;padding:12px 14px;background:{bg_claro};">'
                f'<div style="font-size:15px;font-weight:700;color:#3e3e3e;line-height:1.25;'
                f'word-break:break-word;">{b["titulo"]}</div>'
                f'{sub_html}'
                '</div>'
                f'<div style="flex:none;display:flex;align-items:center;justify-content:center;'
                f'padding:0 14px;background:{bg_claro};border-left:1px solid rgba({r},{g},{bb},0.18);">'
                f'<div style="font-size:13px;font-weight:700;color:{cor};white-space:nowrap;">{ini}</div>'
                '</div>'
                '</div>'
            )
        lista = "".join(cards)

    return f"""<div class="gf-view-mobile">
<div style="padding:12px 14px 90px 14px;max-width:600px;margin:0 auto;">
    {cabecalho}
    {lista}
</div>
</div>"""


def render_espelho_responsivo(db, data):
    """HTML responsivo: grade no desktop, lista colorida no mobile.

    A escolha é feita por CSS media query dentro do próprio iframe, então
    funciona no primeiro carregamento mesmo antes do Python saber a largura.
    Retorna (html, total_de_blocos) ou (None, 0).
    """
    blocos, cores, nomes, total = _carregar_blocos(db, data)
    if not cores:
        return None, 0

    html_grade = _html_grade(db, data, blocos, cores)
    html_lista = _html_lista(data, blocos)

    doc = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
    html, body {{ margin:0; padding:0; background:#fdf8f7;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    .gf-view-mobile {{ display:none; }}
    .gf-view-desktop {{ display:block; }}
    .fab {{ position:fixed; bottom:22px; right:18px; width:56px; height:56px;
            border-radius:50%; background:#5a4038; color:#fff; font-size:32px;
            line-height:56px; text-align:center; box-shadow:0 4px 10px rgba(0,0,0,.35);
            cursor:pointer; z-index:100; border:none; -webkit-tap-highlight-color:transparent; }}
    @media (max-width: 768px) {{
        .gf-view-desktop {{ display:none !important; }}
        .gf-view-mobile {{ display:block !important; }}
        body {{ background:#fdf8f7; }}
    }}
</style>
</head>
<body>
{html_grade}
{html_lista}
<div class="fab" onclick="acionar('agx-esp-novo-08:00')" title="Novo agendamento">+</div>
<script>{_JS_PONTE}{_JS_ALTURA}</script>
</body>
</html>"""
    return doc, total


def render_espelho_google(db, data):
    """HTML completo da grade-espelho do Google para a data escolhida.

    Mantido para compatibilidade. Retorna (html, total_de_blocos) ou None.
    """
    blocos, cores, nomes, total = _carregar_blocos(db, data)
    if not cores:
        return None
    html_grade = _html_grade(db, data, blocos, cores)
    doc = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    html, body {{ margin:0; padding:0; background:#fff;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
</style>
</head>
<body>
{html_grade}
<script>{_JS_PONTE}</script>
</body>
</html>"""
    return doc, total


def render_lista_mobile(db, data, hoje=None):
    """HTML completo da lista mobile.

    Mantido para compatibilidade. Retorna (html, total_de_blocos).
    """
    blocos, cores, nomes, total = _carregar_blocos(db, data)
    if not cores:
        return None, 0
    html_lista = _html_lista(data, blocos, hoje=hoje)
    doc = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
    html, body {{ margin:0; padding:0; background:#fdf8f7;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    .fab {{ position:fixed; bottom:22px; right:18px; width:56px; height:56px;
            border-radius:50%; background:#5a4038; color:#fff; font-size:32px;
            line-height:56px; text-align:center; box-shadow:0 4px 10px rgba(0,0,0,.35);
            cursor:pointer; z-index:100; border:none; -webkit-tap-highlight-color:transparent; }}
</style>
</head>
<body>
{html_lista}
<div class="fab" onclick="acionar('agx-esp-novo-08:00')" title="Novo agendamento">+</div>
<script>{_JS_PONTE}</script>
</body>
</html>"""
    return doc, total


def listar_blocos_editaveis(db, data):
    """Blocos do dia (com vínculo no Google) para edição via popover.

    Ordenados por horário; retorna [(id_do_agendamento, rotulo)].
    """
    from models.schedule import ScheduledAppointment
    from models.google_sync import GoogleEvento

    links = (
        db.query(GoogleEvento.agendamento_id)
        .join(ScheduledAppointment, GoogleEvento.agendamento_id == ScheduledAppointment.id)
        .filter(ScheduledAppointment.data == data)
        .all()
    )
    ids = {l[0] for l in links}
    if not ids:
        return []
    ags = (
        db.query(ScheduledAppointment)
        .filter(ScheduledAppointment.id.in_(ids))
        .order_by(ScheduledAppointment.hora_inicio.asc(), ScheduledAppointment.cliente_nome.asc())
        .all()
    )
    saida = []
    for a in ags:
        partes = [a.hora_inicio or "", (a.cliente_nome or "").strip() or "(sem título)"]
        if a.procedimento:
            partes.append(a.procedimento)
        saida.append((a.id, " · ".join(p for p in partes if p)))
    return saida
