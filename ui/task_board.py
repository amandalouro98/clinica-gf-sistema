import html

import streamlit as st

from services.tasks import (
    STATUS_TAREFA,
    atualizar_tarefa,
    atualizar_status_tarefa,
    criar_tarefa,
    listar_responsaveis,
    listar_tarefas,
    pode_gerenciar_tarefas,
)
from models.user import User
from utils.db import SessionLocal


_CORES_STATUS = {
    "A fazer": ("#c93636", "#fff0f0"),
    "Em andamento": ("#b77900", "#fff5d6"),
    "Concluído": ("#16834b", "#e7f7ee"),
}


def _badge_status(status):
    cor, fundo = _CORES_STATUS.get(status, _CORES_STATUS["A fazer"])
    texto = html.escape(status or "A fazer")
    return (
        f"<span style='display:inline-block;padding:5px 11px;border-radius:999px;"
        f"background:{fundo};color:{cor};font-weight:650;font-size:0.82rem;"
        f"white-space:nowrap'>{texto}</span>"
    )


def _responsaveis_disponiveis(db):
    responsaveis = listar_responsaveis(db)
    if not responsaveis and st.session_state.get("db_demo"):
        demo_user = db.query(User).filter_by(email="responsavel-demo@clinica.local").first()
        if demo_user is None:
            demo_user = User(
                nome="Usuário de demonstração",
                email="responsavel-demo@clinica.local",
                senha_hash="demo",
                perfil="recepcao",
                ativo=True,
            )
            db.add(demo_user)
        else:
            demo_user.ativo = True
        db.commit()
        responsaveis = [demo_user]
    return responsaveis


@st.dialog("Nova tarefa")
def _dialog_nova_tarefa():
    user = st.session_state.get("user") or {}
    perfil = user.get("perfil", "")
    db = SessionLocal()
    try:
        responsaveis = _responsaveis_disponiveis(db)
        if not responsaveis:
            st.warning("Cadastre um usuário ativo para atribuir uma tarefa.")
            if st.button("Fechar", key="task_new_close_empty"):
                st.session_state["task_dialog_open"] = False
                st.rerun()
            return

        versao = st.session_state.get("task_new_version", 0)
        ids = [p.id for p in responsaveis]
        nomes = {p.id: p.nome for p in responsaveis}
        with st.form(f"task_new_form_{versao}"):
            titulo = st.text_input("Tarefa", max_chars=500, key=f"task_new_title_{versao}")
            responsavel_id = st.selectbox(
                "Responsável",
                ids,
                format_func=lambda user_id: nomes[user_id],
                key=f"task_new_owner_{versao}",
            )
            status = st.selectbox("Status", STATUS_TAREFA, key=f"task_new_status_{versao}")
            salvar = st.form_submit_button("Salvar tarefa", type="primary", use_container_width=True)

        cancelar = st.button("Cancelar", key=f"task_new_cancel_{versao}", use_container_width=True)
        if cancelar:
            st.session_state["task_dialog_open"] = False
            st.rerun()
        if salvar:
            try:
                criar_tarefa(db, perfil, titulo, status, responsavel_id)
            except (ValueError, PermissionError) as erro:
                st.error(str(erro))
            else:
                st.session_state["task_dialog_open"] = False
                st.session_state["task_new_version"] = versao + 1
                st.toast("Tarefa cadastrada.")
                st.rerun()
    finally:
        db.close()


def _render_editar_tarefa(tarefa, responsaveis, perfil):
    versao = st.session_state.get(f"task_edit_version_{tarefa.id}", 0)
    ids = [p.id for p in responsaveis]
    nomes = {p.id: p.nome for p in responsaveis}
    if tarefa.responsavel_id not in ids:
        ids.append(responsaveis[0].id)
    owner_index = ids.index(tarefa.responsavel_id) if tarefa.responsavel_id in ids else 0
    with st.popover("✎", help="Editar tarefa"):
        with st.form(f"task_edit_form_{tarefa.id}_{versao}"):
            titulo = st.text_input(
                "Tarefa",
                value=tarefa.titulo,
                max_chars=500,
                key=f"task_edit_title_{tarefa.id}_{versao}",
            )
            responsavel_id = st.selectbox(
                "Responsável",
                ids,
                index=owner_index,
                format_func=lambda user_id: nomes.get(user_id, "Usuário inativo"),
                key=f"task_edit_owner_{tarefa.id}_{versao}",
            )
            status = st.selectbox(
                "Status",
                STATUS_TAREFA,
                index=STATUS_TAREFA.index(tarefa.status) if tarefa.status in STATUS_TAREFA else 0,
                key=f"task_edit_status_{tarefa.id}_{versao}",
            )
            salvar = st.form_submit_button("Salvar alterações", type="primary", use_container_width=True)
        if salvar:
            db_edit = SessionLocal()
            try:
                atualizar_tarefa(
                    db=db_edit,
                    perfil=perfil,
                    tarefa_id=tarefa.id,
                    titulo=titulo,
                    status=status,
                    responsavel_id=responsavel_id,
                )
            except (ValueError, PermissionError) as erro:
                st.error(str(erro))
            else:
                st.session_state[f"task_edit_version_{tarefa.id}"] = versao + 1
                st.toast("Tarefa atualizada.")
                st.rerun()
            finally:
                db_edit.close()


def _salvar_status_direto(tarefa_id):
    status = st.session_state.get(f"task_status_{tarefa_id}")
    db_status = SessionLocal()
    try:
        atualizar_status_tarefa(
            db=db_status,
            perfil=st.session_state.get("user", {}).get("perfil", ""),
            tarefa_id=tarefa_id,
            status=status,
        )
        st.toast("Status atualizado.")
    except (ValueError, PermissionError):
        db_status.rollback()
    finally:
        db_status.close()


def render_task_board(db, perfil):
    pode_editar = pode_gerenciar_tarefas(perfil)
    tarefas = listar_tarefas(db)
    responsaveis = _responsaveis_disponiveis(db) if pode_editar else []

    st.markdown(
        """
        <style>
        .task-board-heading { margin: 0.2rem 0 0.45rem; color: #684848; font-size: 1.2rem; font-weight: 650; }
        .task-board-shell { background: #ffffff; border: 1px solid #eee5e2; border-radius: 12px; padding: 0.4rem 0.6rem; box-shadow: 0 2px 10px rgba(91, 64, 53, 0.06); }
        .task-board-header { color: #8b6a6a; font-size: 0.82rem; font-weight: 650; padding: 0.25rem 0 0.45rem; }
        .task-board-title { color: #4a3030; font-size: 0.95rem; font-weight: 550; overflow-wrap: anywhere; min-height: 2.8rem; display: flex; align-items: center; }
        .task-board-owner { color: #674f4f; font-size: 0.9rem; overflow-wrap: anywhere; min-height: 2.8rem; display: flex; align-items: center; }
        .task-board-status { min-height: 2.8rem; display: flex; align-items: center; }
        .task-board-status [data-baseweb="select"] { font-size: 0.95rem !important; font-weight: 650 !important; }
        .task-board-status [data-testid="stMarkdownContainer"] { width: 100%; }
        .task-board-status .stSelectbox { width: 100%; }
        </style>
        <div class="task-board-heading">Quadro de tarefas</div>
        """,
        unsafe_allow_html=True,
    )

    header = st.columns([2.0, 1.55, 1.45], gap="small")
    for coluna, rotulo in zip(header, ("Tarefa", "Status", "Responsável")):
        coluna.markdown(f"<div class='task-board-header'>{rotulo}</div>", unsafe_allow_html=True)

    with st.container(height=350, border=True):
        if not tarefas:
            st.caption("Nenhuma tarefa cadastrada.")
        for tarefa, responsavel_nome in tarefas:
            st.markdown("<div class='task-board-shell'>", unsafe_allow_html=True)
            col_tarefa, col_status, col_resp = st.columns([2.0, 1.55, 1.45], gap="small", vertical_alignment="center")
            if pode_editar and responsaveis:
                titulo_col, editar_col = col_tarefa.columns([5, 0.5], gap="small", vertical_alignment="center")
                titulo_col.markdown(
                    f"<div class='task-board-title'>{html.escape(tarefa.titulo)}</div>",
                    unsafe_allow_html=True,
                )
                with editar_col:
                    _render_editar_tarefa(tarefa, responsaveis, perfil)
            else:
                col_tarefa.markdown(
                    f"<div class='task-board-title'>{html.escape(tarefa.titulo)}</div>",
                    unsafe_allow_html=True,
                )
            with col_status:
                st.markdown(
                    f"<div class='task-board-status'>{_badge_status(tarefa.status)}</div>",
                    unsafe_allow_html=True,
                )
                if pode_editar and responsaveis:
                    st.selectbox(
                        "Status",
                        STATUS_TAREFA,
                        index=STATUS_TAREFA.index(tarefa.status) if tarefa.status in STATUS_TAREFA else 0,
                        key=f"task_status_{tarefa.id}",
                        label_visibility="collapsed",
                        on_change=_salvar_status_direto,
                        args=(tarefa.id,),
                    )
            col_resp.markdown(
                f"<div class='task-board-owner'>{html.escape(responsavel_nome or 'Sem responsável')}</div>",
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

    if pode_editar:
        colunas_botao = st.columns([1, 1, 1])
        with colunas_botao[1]:
            if st.button("NOVA TAREFA", key="task_open_create", help="Cadastrar nova tarefa", use_container_width=True, type="primary"):
                st.session_state["task_dialog_open"] = True
                st.rerun()
        if st.session_state.get("task_dialog_open"):
            _dialog_nova_tarefa()
