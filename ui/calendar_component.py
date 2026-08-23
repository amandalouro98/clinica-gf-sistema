"""Componente FullCalendar para agenda interativa."""

import json
import urllib.parse
from datetime import datetime, date


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
    return cor_prof or ag.cor_profissional or "#E3A5C7"


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Converte #RRGGBB para rgba(R,G,B,alpha)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return f"rgba(227, 165, 199, {alpha})"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def render_fullcalendar(
    agendamentos: list,
    view: str = "timeGridDay",
    date_str: str = None,
    resources: list = None,
    height: str = "700px",
) -> str:
    """Gera HTML/JS do FullCalendar com eventos e recursos.

    Args:
        agendamentos: lista de dicts com id, title, start, end, resourceId, color, extendedProps
        view: timeGridDay, timeGridWeek, dayGridMonth, listDay, listWeek, listMonth
        date_str: data inicial no formato YYYY-MM-DD
        resources: lista de dicts com id e title
        height: altura do calendário
    """
    events_json = json.dumps(agendamentos, ensure_ascii=False, default=str)
    resources_json = json.dumps(resources or [], ensure_ascii=False, default=str)
    initial_date = date_str or datetime.now().strftime("%Y-%m-%d")

    # Determina se a visualização é lista
    is_list = view.startswith("list")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.15/main.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.15/main.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.15/locales/pt-br.js"></script>
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                font-family: sans-serif;
                font-size: 13px;
            }}
            #calendar {{
                height: {height};
                width: 100%;
            }}
            .fc-event {{
                cursor: pointer;
                border: none !important;
                border-radius: 4px !important;
                font-size: 11px;
                line-height: 1.2;
                padding: 2px 4px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.15);
            }}
            .fc-event-title {{
                font-weight: 600;
                white-space: normal !important;
            }}
            .fc-event-time {{
                font-size: 10px;
                opacity: 0.9;
            }}
            .fc-toolbar-title {{
                font-size: 16px !important;
            }}
            .fc-button {{
                font-size: 12px !important;
                padding: 4px 8px !important;
            }}
            .fc-col-header-cell-cushion {{
                font-size: 12px;
            }}
            .fc-list-event-graphic {{
                width: 8px;
            }}
            .fc-list-event-dot {{
                width: 8px;
                height: 8px;
            }}
            .event-menu {{
                position: absolute;
                top: 2px;
                right: 2px;
                z-index: 10;
                cursor: pointer;
                background: rgba(255,255,255,0.25);
                border-radius: 3px;
                padding: 0 3px;
                font-weight: bold;
                color: #fff;
                text-shadow: 0 1px 1px rgba(0,0,0,0.3);
                line-height: 1;
            }}
            .event-menu:hover {{
                background: rgba(255,255,255,0.5);
            }}
        </style>
    </head>
    <body>
        <div id="calendar"></div>
        <script>
            const events = {events_json};
            const resources = {resources_json};

            function navigate(action, id, extra) {{
                const url = new URL(window.location.href);
                url.searchParams.set('agenda_action', action);
                url.searchParams.set('agenda_id', id);
                if (extra) {{
                    for (const [k, v] of Object.entries(extra)) {{
                        url.searchParams.set(k, v);
                    }}
                }}
                // Remove params antigos para evitar conflito
                url.searchParams.delete('agenda_edit');
                url.searchParams.delete('agenda_move');
                window.location.href = url.toString();
            }}

            document.addEventListener('DOMContentLoaded', function() {{
                const calendarEl = document.getElementById('calendar');
                const calendar = new FullCalendar.Calendar(calendarEl, {{
                    locale: 'pt-br',
                    initialView: '{view}',
                    initialDate: '{initial_date}',
                    headerToolbar: {{
                        left: 'prev,next today',
                        center: 'title',
                        right: 'timeGridDay,timeGridWeek,dayGridMonth,listWeek'
                    }},
                    buttonText: {{
                        today: 'Hoje',
                        month: 'Mês',
                        week: 'Semana',
                        day: 'Dia',
                        list: 'Lista'
                    }},
                    slotMinTime: '07:00:00',
                    slotMaxTime: '21:00:00',
                    slotDuration: '00:30:00',
                    slotLabelInterval: '01:00',
                    allDaySlot: false,
                    nowIndicator: true,
                    editable: true,
                    droppable: true,
                    eventStartEditable: true,
                    eventDurationEditable: false,
                    eventOverlap: true,
                    height: '{height}',
                    resources: resources,
                    resourceAreaHeaderContent: 'Profissionais',
                    views: {{
                        timeGridDay: {{
                            type: 'timeGrid',
                            duration: {{ days: 1 }}
                        }},
                        timeGridWeek: {{
                            type: 'timeGrid',
                            duration: {{ days: 7 }}
                        }}
                    }},
                    events: events,
                    eventContent: function(arg) {{
                        // Render custom: título + horário + menu de 3 pontinhos
                        const div = document.createElement('div');
                        div.style.width = '100%';
                        div.style.position = 'relative';
                        div.style.paddingRight = '14px';
                        div.style.boxSizing = 'border-box';

                        const title = document.createElement('div');
                        title.className = 'fc-event-title';
                        title.innerText = arg.event.title;
                        div.appendChild(title);

                        if (arg.timeText) {{
                            const time = document.createElement('div');
                            time.className = 'fc-event-time';
                            time.innerText = arg.timeText;
                            div.appendChild(time);
                        }}

                        const menu = document.createElement('div');
                        menu.className = 'event-menu';
                        menu.innerText = '⋮';
                        menu.title = 'Opções';
                        menu.onclick = function(e) {{
                            e.stopPropagation();
                            e.preventDefault();
                            const action = window.confirm('Deseja excluir este agendamento?\nClique em OK para excluir ou Cancelar para editar.');
                            if (action) {{
                                navigate('delete', arg.event.id);
                            }} else {{
                                navigate('edit', arg.event.id);
                            }}
                        }};
                        div.appendChild(menu);

                        return {{ domNodes: [div] }};
                    }},
                    eventClick: function(info) {{
                        navigate('edit', info.event.id);
                    }},
                    eventDrop: function(info) {{
                        const evt = info.event;
                        const newDate = evt.start.toISOString().split('T')[0];
                        const newTime = evt.start.toTimeString().slice(0,5);
                        navigate('move', evt.id, {{ new_date: newDate, new_time: newTime }});
                    }},
                    dateClick: function(info) {{
                        // Clique em slot vazio: abre popup de novo agendamento
                        const clickedDate = info.dateStr;
                        navigate('new', '0', {{ date: clickedDate }});
                    }}
                }});
                calendar.render();
            }});
        </script>
    </body>
    </html>
    """
    return html


def agenda_to_events(agendamentos, nomes_prof=None):
    """Converte objetos ScheduledAppointment em eventos do FullCalendar."""
    events = []
    for ag in agendamentos:
        try:
            data_str = ag.data.strftime("%Y-%m-%d") if hasattr(ag.data, "strftime") else str(ag.data)
            start = f"{data_str}T{ag.hora_inicio}:00"
            # Calcula end com base na duração
            from datetime import timedelta
            hora, minuto = map(int, ag.hora_inicio.split(":"))
            end_dt = datetime.strptime(f"{data_str} {ag.hora_inicio}", "%Y-%m-%d %H:%M") + timedelta(minutes=ag.duracao_min or 60)
            end = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

            title = ag.cliente_nome or ag.procedimento or "Sem título"
            if ag.procedimento and ag.cliente_nome:
                title = f"{ag.cliente_nome}"

            resource_id = ag.profissional or "sem-profissional"

            events.append({
                "id": str(ag.id),
                "title": title,
                "start": start,
                "end": end,
                "resourceId": resource_id,
                "color": _cor_final_agendamento(ag),
                "textColor": "#ffffff",
                "extendedProps": {
                    "profissional": ag.profissional or "",
                    "procedimento": ag.procedimento or "",
                    "sala": ag.sala or "",
                    "confirmado": ag.confirmado,
                },
            })
        except Exception:
            continue
    return events


def build_resources(profissionais, preferencias_ordem=None):
    """Monta lista de recursos (profissionais) para o FullCalendar."""
    recursos = []
    vistos = set()
    # Ordem preferencial: Gabi à direita, demais à esquerda
    if preferencias_ordem:
        for nome in preferencias_ordem:
            if nome and nome not in vistos:
                vistos.add(nome)
                recursos.append({"id": nome, "title": nome})
    for p in profissionais:
        nome = p.nome if hasattr(p, "nome") else p
        if nome and nome not in vistos:
            vistos.add(nome)
            recursos.append({"id": nome, "title": nome})
    return recursos
