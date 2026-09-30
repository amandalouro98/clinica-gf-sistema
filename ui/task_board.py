import html

import streamlit as st

from services.tasks import (
    STATUS_TAREFA,
    atualizar_tarefa,
    atualizar_status_tarefa,
    criar_tarefa,
    excluir_tarefa,
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


def _cor_fundo_status(status):
    return _CORES_STATUS.get(status, _CORES_STATUS["A fazer"])[1]


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


def _form_nova_tarefa(perfil):
    db = SessionLocal()
    try:
        responsaveis = _responsaveis_disponiveis(db)
        if not responsaveis:
            st.warning("Cadastre um usuário ativo para atribuir uma tarefa.")
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
        if salvar:
            try:
                criar_tarefa(db, perfil, titulo, status, responsavel_id)
            except (ValueError, PermissionError) as erro:
                st.error(str(erro))
            else:
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
    with st.popover("✎", help="Editar ou excluir tarefa"):
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

        st.divider()
        confirmar = st.checkbox(
            "Confirmar exclusão",
            key=f"task_del_check_{tarefa.id}",
        )
        if st.button(
            "🗑 Excluir tarefa",
            key=f"task_del_btn_{tarefa.id}",
            disabled=not confirmar,
            use_container_width=True,
        ):
            db_del = SessionLocal()
            try:
                excluir_tarefa(db_del, perfil, tarefa.id)
            except (ValueError, PermissionError) as erro:
                st.error(str(erro))
            else:
                st.session_state.pop(f"task_del_check_{tarefa.id}", None)
                st.toast("Tarefa excluída.")
                st.rerun()
            finally:
                db_del.close()


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

    # Regras de cor do campo de status — um único bloco de CSS para todas as tarefas
    regras_status = ""
    if pode_editar:
        for tarefa, _ in tarefas:
            status_bg = _cor_fundo_status(tarefa.status)
            regras_status += (
                f".st-key-task_status_{tarefa.id} [data-baseweb='select'] > div:first-child,"
                f".st-key-task_status_{tarefa.id} [data-baseweb='select'] > div:first-child > div"
                f"{{background-color:{status_bg} !important;border-color:{status_bg} !important;"
                f"border-radius:7px !important;}}"
            )

    st.markdown(
        f"""
        <style>
        .task-board-heading {{ margin: 0.2rem 0 0.45rem; color: #684848; font-size: 1.15rem; font-weight: 650; }}
        .task-board-header {{ color: #8b6a6a; font-size: 0.8rem; font-weight: 650; padding: 0.25rem 0 0.4rem; }}
        .task-board-title {{ color: #4a3030; font-size: 0.88rem; font-weight: 550; overflow-wrap: anywhere; min-height: 2.25rem; display: flex; align-items: center; }}
        .task-board-owner {{ color: #674f4f; font-size: 0.84rem; overflow-wrap: anywhere; min-height: 2.25rem; display: flex; align-items: center; }}
        .task-board-status {{ min-height: 2.25rem; display: flex; align-items: center; }}
        .task-board-status [data-baseweb="select"] {{ font-size: 0.88rem !important; font-weight: 650 !important; }}
        .task-board-status .stSelectbox {{ width: 100%; }}
        .task-board-row-separator {{ height: 1px; background: #eee5e2; margin: 0.15rem 0; }}
        {regras_status}
        </style>
        <div class="task-board-heading">Quadro de tarefas</div>
        """,
        unsafe_allow_html=True,
    )

    header = st.columns([2.15, 0.45, 1.45, 1.35], gap="small")
    for coluna, rotulo in zip(header, ("Tarefa", "", "Status", "Responsável")):
        coluna.markdown(f"<div class='task-board-header'>{rotulo}</div>", unsafe_allow_html=True)

    with st.container(height=290, border=True):
        if not tarefas:
            st.caption("Nenhuma tarefa cadastrada.")
        for tarefa, responsavel_nome in tarefas:
            col_tarefa, col_editar, col_status, col_resp = st.columns(
                [2.15, 0.45, 1.45, 1.35],
                gap="small",
                vertical_alignment="center",
            )
            col_tarefa.markdown(
                f"<div class='task-board-title'>{html.escape(tarefa.titulo)}</div>",
                unsafe_allow_html=True,
            )
            if pode_editar and responsaveis:
                with col_editar:
                    _render_editar_tarefa(tarefa, responsaveis, perfil)
                with col_status:
                    st.selectbox(
                        "Status",
                        STATUS_TAREFA,
                        index=STATUS_TAREFA.index(tarefa.status) if tarefa.status in STATUS_TAREFA else 0,
                        key=f"task_status_{tarefa.id}",
                        label_visibility="collapsed",
                        on_change=_salvar_status_direto,
                        args=(tarefa.id,),
                    )
            else:
                with col_status:
                    st.markdown(
                        f"<div class='task-board-status'>{_badge_status(tarefa.status)}</div>",
                        unsafe_allow_html=True,
                    )
            col_resp.markdown(
                f"<div class='task-board-owner'>{html.escape(responsavel_nome or 'Sem responsável')}</div>",
                unsafe_allow_html=True,
            )
            st.markdown("<div class='task-board-row-separator'></div>", unsafe_allow_html=True)

    if pode_editar:
        with st.popover("NOVA TAREFA", use_container_width=True):
            _form_nova_tarefa(perfil)
