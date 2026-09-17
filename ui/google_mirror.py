"""Espelho visual do Google Calendar dentro do sistema.

Grade no estilo do Google (visão de dia): uma coluna por calendário
(profissionais e salas), blocos coloridos posicionados pela duração e
linha vermelha no horário atual. Mostra SOMENTE eventos vindos do Google
(agendamentos com vínculo em GoogleEvento).
"""
import html
from datetime import datetime, timedelta, timezone

BR_TZ = timezone(timedelta(hours=-3))

# Janela de exibição da grade (horas cheias)
HORA_INI = 7   # 07:00
HORA_FIM = 22  # 22:00
PX_POR_HORA = 56


def _minutos(texto, padrao=0):
    try:
        hh, mm = str(texto or "00:00").split(":")[:2]
        return int(hh) * 60 + int(mm)
    except Exception:
        return padrao


def render_espelho_google(db, data):
    """Renderiza a grade-espelho do Google para a data escolhida."""
    from models.professional import Professional
    from models.room import Room
    from models.schedule import ScheduledAppointment
    from models.google_sync import GoogleEvento

    # ── colunas: calendários mapeados (profissionais primeiro, depois salas) ──
    colunas = []  # [(calendar_id, nome, cor, tipo)]
    for p in db.query(Professional).order_by(Professional.nome.asc()).all():
        if p.google_calendar_id:
            colunas.append((p.google_calendar_id, p.nome, p.cor or "#E3A5C7", "prof"))
    for r in db.query(Room).order_by(Room.nome.asc()).all():
        if r.google_calendar_id:
            colunas.append((r.google_calendar_id, r.nome, r.cor or "#E3A5C7", "sala"))
    if not colunas:
        return None
    cor_por_cal = {c[0]: c[2] for c in colunas}

    # ── eventos do dia com vínculo no Google ──
    links = (
        db.query(GoogleEvento, ScheduledAppointment)
        .join(ScheduledAppointment, GoogleEvento.agendamento_id == ScheduledAppointment.id)
        .filter(ScheduledAppointment.data == data)
        .all()
    )

    blocos_por_col = {c[0]: [] for c in colunas}
    for link, ag in links:
        if link.calendar_id not in blocos_por_col:
            continue
        ini_m = _minutos(ag.hora_inicio, HORA_INI * 60)
        fim_m = _minutos(ag.hora_fim, ini_m + (ag.duracao_min or 60))
        dur = max(20, fim_m - ini_m)
        titulo = (ag.cliente_nome or "").strip() or "(sem título)"
        sub = ag.hora_inicio or ""
        if ag.procedimento:
            titulo = f"{titulo} · {ag.procedimento}"
        dica = f"{ag.hora_inicio}–{ag.hora_fim} · {titulo}"
        if ag.sala:
            dica += f" · {ag.sala}"
        if getattr(ag, "pre_agendamento", False):
            dica += " · pré-agendamento"
        elif ag.confirmado:
            dica += " · confirmado"
        blocos_por_col[link.calendar_id].append({
            "ini": ini_m, "dur": dur,
            "titulo": html.escape(titulo),
            "sub": html.escape(sub),
            "dica": html.escape(dica),
        })

    # ordena por horário de início
    for cal in blocos_por_col:
        blocos_por_col[cal].sort(key=lambda b: b["ini"])

    # ── linha do horário atual (só se for hoje) ──
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

    # ── eixo de horas (coluna própria, à esquerda da grade) ──
    altura = (HORA_FIM - HORA_INI) * PX_POR_HORA
    marcas = []
    for h in range(HORA_INI, HORA_FIM + 1):
        top = (h - HORA_INI) * PX_POR_HORA
        marcas.append(
            f'<div style="position:absolute;top:{top}px;left:0;width:100%;'
            'border-top:1px solid #eee;"></div>'
        )
    eixo = []
    for h in range(HORA_INI, HORA_FIM + 1):
        top = (h - HORA_INI) * PX_POR_HORA
        eixo.append(
            f'<div style="position:absolute;top:{top - 7}px;left:0;width:46px;'
            'text-align:right;font-size:11px;color:#999;padding-right:4px;'
            f'background:#fff;z-index:2;">{h:02d}:00</div>'
        )

    # ── colunas com blocos ──
    total = (HORA_FIM - HORA_INI) * 60
    html_cols = []
    for cal_id, nome, cor, _tipo in colunas:
        blocos_html = []
        for b in blocos_por_col[cal_id]:
            top_pct = max(0.0, (b["ini"] - HORA_INI * 60) / total * 100)
            alt_pct = b["dur"] / total * 100
            blocos_html.append(
                f'<div title="{b["dica"]}" style="position:absolute;'
                f'top:calc({top_pct:.3f}% + 1px);height:calc({alt_pct:.3f}% - 2px);'
                f'left:2px;right:2px;background:{cor};border-radius:6px;'
                'padding:3px 5px;overflow:hidden;color:#fff;z-index:3;'
                'box-shadow:0 1px 2px rgba(0,0,0,.25);cursor:default;">'
                f'<div style="font-size:11px;font-weight:600;line-height:1.2;'
                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{b["titulo"]}</div>'
                f'<div style="font-size:10px;opacity:.9;">{b["sub"]}</div>'
                '</div>'
            )
        html_cols.append(
            f'<div style="flex:1;min-width:130px;position:relative;'
            f'border-left:1px solid #eee;">{linha_agora}{"".join(blocos_html)}</div>'
        )

    cabecalhos = "".join(
        f'<div style="flex:1;min-width:130px;padding:6px 4px;text-align:center;">'
        f'<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:50%;background:{cor};margin-right:5px;"></span>'
        f'<span style="font-size:12px;font-weight:600;color:#5a4038;">{html.escape(nome)}</span>'
        f'</div>'
        for _cal, nome, cor, _t in colunas
    )

    total_blocos = sum(len(v) for v in blocos_por_col.values())
    grid = (
        '<div style="border:1px solid #f0d5ce;border-radius:12px;overflow:hidden;'
        'background:#fff;">'
        f'<div style="display:flex;border-bottom:1px solid #f0d5ce;background:#fdf6f4;">'
        f'<div style="width:52px;flex:none;"></div>{cabecalhos}</div>'
        '<div style="overflow-x:auto;">'
        f'<div style="display:flex;min-width:100%;">'
        # coluna fixa do eixo de horas (com fundo branco, nunca atrás dos blocos)
        f'<div style="width:52px;flex:none;position:relative;height:{altura}px;'
        f'background:#fff;z-index:4;border-right:1px solid #eee;">{"".join(eixo)}</div>'
        # grade: linhas de hora por trás, colunas por cima
        f'<div style="flex:1;position:relative;height:{altura}px;">'
        f'<div style="position:absolute;inset:0;z-index:1;">{"".join(marcas)}</div>'
        f'<div style="display:flex;position:absolute;inset:0;z-index:2;">'
        f'{"".join(html_cols)}'
        '</div>'
        '</div>'
        '</div></div></div>'
    )
    return grid, total_blocos


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
