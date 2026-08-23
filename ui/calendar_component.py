"""Componente FullCalendar para agenda interativa."""

import json
from datetime import datetime, timedelta


# Paleta do sistema (espelha .streamlit/config.toml)
COR_PRIMARIA = "#D59C9C"
COR_PRIMARIA_ESCURA = "#b87575"
COR_TEXTO = "#4a3030"
COR_BORDA = "#f0d5ce"
COR_FUNDO_HOJE = "#fff0ee"
COR_FOCO = "rgba(213, 156, 156, 0.45)"


CORES_PROFISSIONAIS = {
    "Rosa": "#F4A7B9",
    "Lavanda": "#C9A7F4",
    "Azul": "#A7D4F4",
    "Verde": "#A7F4C9",
    "Amarelo": "#F4E4A7",
    "Laranja": "#F4C4A7",
    "Vermelho": "#F4A7A7",
    "Cinza": "#C8C8C8",
}

CORES_ESPECIAIS = {
    "ju": "#8A2BE2",      # roxo
    "gabi": "#1E3A5F",    # azul escuro
    "kauane": "#808080",  # cinza
    "sala 2": "#FFC0CB",  # rosa
    "sala 3": "#FFD700",  # amarelo
}


def _cor_final_agendamento(ag, cor_prof=None):
    """Retorna a cor final do agendamento considerando profissional e sala."""
    # Salas alugáveis têm cor fixa
    if ag.sala:
        sala_lower = ag.sala.lower()
        if "sala 2" in sala_lower:
            return CORES_ESPECIAIS.get("sala 2", "#FFC0CB")
        if "sala 3" in sala_lower:
            return CORES_ESPECIAIS.get("sala 3", "#FFD700")
        # Sala 1 e Soroterapia seguem a cor do profissional
    # Profissionais específicos
    nome_prof = (ag.profissional or "").strip().lower()
    if nome_prof:
        for chave, cor in CORES_ESPECIAIS.items():
            if chave in nome_prof:
                return cor
    # Fallback: cor do cadastro do profissional
    return cor_prof or getattr(ag, "cor_profissional", None) or "#E3A5C7"


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Converte #RRGGBB para rgba(R,G,B,alpha)."""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return f"rgba(227, 165, 199, {alpha})"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


# Views suportadas pelo bundle gratuito do FullCalendar v6
_VIEWS_VALIDAS = {
    "timeGridDay",
    "timeGridWeek",
    "dayGridMonth",
    "dayGridWeek",
    "dayGridDay",
    "listDay",
    "listWeek",
    "listMonth",
}


def render_fullcalendar(
    agendamentos: list,
    view: str = "timeGridDay",
    date_str: str = None,
    resources: list = None,
    height: str = "700px",
    titulo: str = None,
    show_toolbar: bool = True,
) -> str:
    """Gera HTML/JS do FullCalendar com eventos.

    Usa o bundle gratuito do FullCalendar v6 (index.global.min.js).
    O parâmetro `resources` é aceito por compatibilidade, mas não é usado:
    colunas por recurso exigem o plugin pago (Scheduler).

    Args:
        agendamentos: lista de dicts com id, title, start, end, cores, extendedProps
        view: timeGridDay, timeGridWeek, dayGridMonth, listDay, listWeek, listMonth
        date_str: data inicial no formato YYYY-MM-DD
        resources: ignorado (compatibilidade)
        height: altura do calendário
        titulo: rótulo opcional exibido acima do calendário
        show_toolbar: exibe ou não a barra de navegação do FullCalendar
    """
    fc_view = view if view in _VIEWS_VALIDAS else "timeGridDay"

    events_json = json.dumps(agendamentos or [], ensure_ascii=False, default=str)
    initial_date = date_str or datetime.now().strftime("%Y-%m-%d")

    if show_toolbar:
        toolbar_json = json.dumps({
            "left": "prev,next today",
            "center": "title",
            "right": "timeGridDay,timeGridWeek,dayGridMonth,listWeek",
        })
    else:
        toolbar_json = "false"

    titulo_html = ""
    if titulo:
        titulo_html = (
            f'<div style="font-weight:700;font-size:13px;padding:6px 4px;'
            f'color:{COR_PRIMARIA_ESCURA};">{titulo}</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.15/index.global.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@fullcalendar/core@6.1.15/locales/pt-br.global.min.js"></script>
<style>
    html, body {{
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 13px;
        background: transparent;
        color: {COR_TEXTO};
    }}
    #calendar {{
        width: 100%;
        background: #ffffff;
        border-radius: 10px;
        padding: 8px;
        box-sizing: border-box;
        border: 1px solid {COR_BORDA};
    }}
    /* Grade em branco, no padrao do sistema */
    .fc {{ --fc-page-bg-color: #ffffff; }}
    .fc .fc-scrollgrid,
    .fc .fc-scrollgrid-section > * {{ background: #ffffff; }}
    .fc .fc-timegrid-slot,
    .fc .fc-daygrid-day {{ background: #ffffff; }}
    .fc .fc-day-today {{ background: {COR_FUNDO_HOJE} !important; }}
    .fc .fc-theme-standard td,
    .fc .fc-theme-standard th,
    .fc .fc-scrollgrid {{ border-color: {COR_BORDA} !important; }}
    .fc .fc-timegrid-slot-label,
    .fc .fc-col-header-cell-cushion,
    .fc .fc-list-day-text,
    .fc .fc-list-day-side-text {{ color: {COR_TEXTO}; }}

    /* Botoes dia / semana / mes na cor do sistema */
    .fc .fc-button-primary {{
        background-color: {COR_PRIMARIA} !important;
        border-color: {COR_PRIMARIA} !important;
        color: #ffffff !important;
        font-weight: 600;
        box-shadow: none !important;
    }}
    .fc .fc-button-primary:hover {{
        background-color: {COR_PRIMARIA_ESCURA} !important;
        border-color: {COR_PRIMARIA_ESCURA} !important;
    }}
    .fc .fc-button-primary:disabled {{
        background-color: {COR_PRIMARIA} !important;
        border-color: {COR_PRIMARIA} !important;
        opacity: 0.5;
    }}
    .fc .fc-button-primary:not(:disabled).fc-button-active,
    .fc .fc-button-primary:not(:disabled):active {{
        background-color: {COR_PRIMARIA_ESCURA} !important;
        border-color: {COR_PRIMARIA_ESCURA} !important;
    }}
    .fc .fc-button-primary:focus,
    .fc .fc-button-primary:not(:disabled).fc-button-active:focus {{
        box-shadow: 0 0 0 2px {COR_FOCO} !important;
    }}
    .fc .fc-toolbar-title {{
        font-size: 15px !important;
        color: {COR_TEXTO};
        font-weight: 700;
    }}
    .fc .fc-button {{ font-size: 11px !important; padding: 3px 9px !important; border-radius: 7px !important; }}

    .fc .fc-event {{
        cursor: pointer;
        border: none !important;
        border-radius: 6px !important;
        font-size: 11px;
        line-height: 1.2;
        padding: 1px 3px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.15);
    }}
    .fc .fc-event-title {{ font-weight: 600; white-space: normal !important; }}
    .fc .fc-event-time {{ font-size: 10px; opacity: 0.9; }}
    .fc .fc-col-header-cell-cushion {{ font-size: 12px; font-weight: 600; }}
    .fc .fc-timegrid-slot {{ height: 1.7em; }}
    .fc .fc-timegrid-now-indicator-line {{ border-color: {COR_PRIMARIA_ESCURA}; }}
    .fc-erro {{
        padding: 16px;
        color: #b91c1c;
        background: #fef2f2;
        border-radius: 8px;
        font-size: 13px;
    }}
    .serie-badge {{
        display: inline-block;
        background: rgba(255,255,255,0.32);
        border-radius: 4px;
        padding: 0 3px;
        font-size: 9px;
        font-weight: 700;
        margin-right: 3px;
    }}
    .event-acoes {{
        position: absolute;
        top: 1px;
        right: 2px;
        z-index: 5;
        display: flex;
        gap: 3px;
        line-height: 1;
    }}
    .event-acao {{
        cursor: pointer;
        font-size: 11px;
        background: rgba(255,255,255,0.30);
        border-radius: 3px;
        padding: 1px 2px;
    }}
    .event-acao:hover {{ background: rgba(255,255,255,0.65); }}
</style>
</head>
<body>
{titulo_html}
<div id="calendar"></div>
<script>
(function() {{
    var events = {events_json};
    var headerToolbar = {toolbar_json};

    function navigate(action, id, extra) {{
        try {{
            var target = (window.parent && window.parent !== window) ? window.parent : window;
            var url = new URL(target.location.href);
            url.searchParams.set('agenda_action', action);
            url.searchParams.set('agenda_id', id);
            if (extra) {{
                Object.keys(extra).forEach(function(k) {{
                    url.searchParams.set(k, extra[k]);
                }});
            }}
            target.location.href = url.toString();
        }} catch (e) {{
            console.error('Falha ao navegar:', e);
        }}
    }}

    function boot() {{
        var el = document.getElementById('calendar');
        if (typeof FullCalendar === 'undefined' || !FullCalendar.Calendar) {{
            el.innerHTML = '<div class="fc-erro">Nao foi possivel carregar o calendario. '
                + 'Verifique a conexao com a internet e recarregue a pagina.</div>';
            return;
        }}
        try {{
            var calendar = new FullCalendar.Calendar(el, {{
                locale: 'pt-br',
                initialView: '{fc_view}',
                initialDate: '{initial_date}',
                headerToolbar: headerToolbar,
                buttonText: {{ today: 'Hoje', month: 'Mes', week: 'Semana', day: 'Dia', list: 'Lista' }},
                slotMinTime: '07:00:00',
                slotMaxTime: '21:00:00',
                slotDuration: '00:30:00',
                slotLabelInterval: '01:00',
                allDaySlot: false,
                nowIndicator: true,
                editable: true,
                eventStartEditable: true,
                eventDurationEditable: false,
                eventOverlap: true,
                expandRows: true,
                height: '{height}',
                events: events,
                eventDidMount: function(info) {{
                    var p = info.event.extendedProps || {{}};
                    var partes = [];
                    if (p.serie_label) partes.push(p.serie_label);
                    if (p.procedimento) partes.push(p.procedimento);
                    if (p.profissional) partes.push(p.profissional);
                    if (p.sala) partes.push(p.sala);
                    info.el.title = info.event.title + (partes.length ? ' - ' + partes.join(' | ') : '');

                    var acoes = document.createElement('div');
                    acoes.className = 'event-acoes';

                    var btnEditar = document.createElement('span');
                    btnEditar.className = 'event-acao';
                    btnEditar.innerText = '\\u270F\\uFE0F';
                    btnEditar.title = 'Editar agendamento';
                    btnEditar.onclick = function(e) {{
                        e.stopPropagation();
                        e.preventDefault();
                        navigate('edit', info.event.id);
                    }};

                    var btnExcluir = document.createElement('span');
                    btnExcluir.className = 'event-acao';
                    btnExcluir.innerText = '\\uD83D\\uDDD1\\uFE0F';
                    btnExcluir.title = 'Excluir agendamento';
                    btnExcluir.onclick = function(e) {{
                        e.stopPropagation();
                        e.preventDefault();
                        navigate('delete', info.event.id);
                    }};

                    acoes.appendChild(btnEditar);
                    acoes.appendChild(btnExcluir);
                    info.el.style.position = 'relative';
                    info.el.appendChild(acoes);
                }},
                eventClick: function(info) {{
                    if (info.jsEvent) {{ info.jsEvent.preventDefault(); }}
                    navigate('edit', info.event.id);
                }},
                eventDrop: function(info) {{
                    var s = info.event.start;
                    if (!s) {{ info.revert(); return; }}
                    var pad = function(n) {{ return (n < 10 ? '0' : '') + n; }};
                    var novaData = s.getFullYear() + '-' + pad(s.getMonth() + 1) + '-' + pad(s.getDate());
                    var novaHora = pad(s.getHours()) + ':' + pad(s.getMinutes());
                    navigate('move', info.event.id, {{ new_date: novaData, new_time: novaHora }});
                }},
                dateClick: function(info) {{
                    navigate('new', '0', {{ date: info.dateStr.slice(0, 10) }});
                }}
            }});
            calendar.render();
        }} catch (err) {{
            console.error(err);
            el.innerHTML = '<div class="fc-erro">Erro ao montar o calendario: '
                + (err && err.message ? err.message : err) + '</div>';
        }}
    }}

    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', boot);
    }} else {{
        boot();
    }}
}})();
</script>
</body>
</html>"""
    return html


def agenda_to_events(agendamentos, nomes_prof=None, series_map=None):
    """Converte objetos ScheduledAppointment em eventos do FullCalendar.

    Args:
        agendamentos: objetos ScheduledAppointment
        nomes_prof: ignorado (compatibilidade)
        series_map: dict {id_agendamento: (posicao, total)} para recorrências.
            Quando informado, o título recebe o sufixo "(1 de 5)".
    """
    events = []
    series_map = series_map or {}
    for ag in agendamentos or []:
        try:
            if hasattr(ag.data, "strftime"):
                data_str = ag.data.strftime("%Y-%m-%d")
            else:
                data_str = str(ag.data)[:10]

            hora_ini = (ag.hora_inicio or "").strip()
            if len(hora_ini) < 4:
                continue
            if len(hora_ini) == 4:  # "9:00" -> "09:00"
                hora_ini = "0" + hora_ini
            inicio_dt = datetime.strptime(f"{data_str} {hora_ini[:5]}", "%Y-%m-%d %H:%M")

            hora_fim = (getattr(ag, "hora_fim", "") or "").strip()
            fim_dt = None
            if len(hora_fim) >= 4:
                if len(hora_fim) == 4:
                    hora_fim = "0" + hora_fim
                try:
                    fim_dt = datetime.strptime(f"{data_str} {hora_fim[:5]}", "%Y-%m-%d %H:%M")
                except ValueError:
                    fim_dt = None
            if not fim_dt or fim_dt <= inicio_dt:
                fim_dt = inicio_dt + timedelta(minutes=getattr(ag, "duracao_min", None) or 60)

            cor = _cor_final_agendamento(ag)

            titulo_evento = ag.cliente_nome or ag.procedimento or "Sem titulo"
            serie_label = ""
            posicao_total = series_map.get(ag.id)
            if posicao_total:
                pos, total = posicao_total
                if total > 1:
                    serie_label = f"{pos} de {total}"
                    titulo_evento = f"{titulo_evento} ({serie_label})"

            events.append({
                "id": str(ag.id),
                "title": titulo_evento,
                "start": inicio_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "end": fim_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "backgroundColor": cor,
                "borderColor": cor,
                "textColor": "#ffffff",
                "extendedProps": {
                    "profissional": ag.profissional or "",
                    "procedimento": ag.procedimento or "",
                    "sala": ag.sala or "",
                    "confirmado": bool(getattr(ag, "confirmado", False)),
                    "serie_label": serie_label,
                },
            })
        except Exception:
            continue
    return events


def build_resources(profissionais, preferencias_ordem=None):
    """Monta lista de recursos (profissionais).

    Mantido por compatibilidade — colunas por recurso exigem o plugin pago.
    """
    recursos = []
    vistos = set()
    if preferencias_ordem:
        for nome in preferencias_ordem:
            if nome and nome not in vistos:
                vistos.add(nome)
                recursos.append({"id": nome, "title": nome})
    for p in profissionais or []:
        nome = p.nome if hasattr(p, "nome") else p
        if nome and nome not in vistos:
            vistos.add(nome)
            recursos.append({"id": nome, "title": nome})
    return recursos
