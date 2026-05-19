import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, datetime, timedelta, timezone

# Fuso horário de Brasília (GMT-3)
BR_TZ = timezone(timedelta(hours=-3))

def _hoje():
    return datetime.now(BR_TZ).date()

def _agora():
    return datetime.now(BR_TZ)
from dotenv import load_dotenv
from streamlit_searchbox import st_searchbox

# ====== CONFIGURAÇÃO INICIAL ======
st.set_page_config(page_title="Gabriela Franco Saúde", page_icon="ui/favicon.png", layout="wide")
load_dotenv()

# ====== IMPORTS DO PROJETO ======
from utils.db import SessionLocal, engine
from sqlalchemy import func
from models.base import Base
from models.user import User
from models.client import Client
from models.assessment import Assessment
from models.stock import Product, StockLote, StockMovement
from models.appointment import Appointment, AppointmentMaterial
from models.biometrics import Biometrics
from models.contract import Contract
from models.schedule import ScheduledAppointment
from models.professional import Professional
from models.sale import Sale, SaleItem, SessionUsage
from models.schedule_log import AgendaLog
from models.dose_table import DoseTable
from models.material import Material
from models.tratamento import Tratamento
from utils.security import hash_password
from utils.helpers import calcular_imc
from services.auth import authenticate, seed_admin
from services.inventory import movimentar, alertas
from services.contracts import gerar_pdf_contrato
from services.importador import sincronizar_clientes
from ui.components import header_titulo, month_from_date

# ====== CRIA O BANCO (SE NÃO EXISTIR) E SEED DO ADMIN ======
Base.metadata.create_all(bind=engine)
seed_admin()

# ====== CSS DO TEMA ======
try:
    with open("ui/style.css", "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except Exception:
    pass

st.markdown("""
<style>
div[data-baseweb="input"] input:disabled,
div[data-baseweb="base-input"] input:disabled,
div[data-baseweb="textarea"] textarea:disabled {
    background-color: #e9eef7 !important;
    color: #1f2937 !important;
    -webkit-text-fill-color: #1f2937 !important;
    opacity: 1 !important;
    cursor: not-allowed !important;
    border-radius: 10px !important;
}
input[disabled], textarea[disabled] {
    background-color: #e9eef7 !important;
    color: #1f2937 !important;
    -webkit-text-fill-color: #1f2937 !important;
    opacity: 1 !important;
}
input[type="checkbox"][disabled] {
    opacity: 0.85 !important;
}
</style>
""", unsafe_allow_html=True)

# ====== SESSÃO / LOGIN ======
if "user" not in st.session_state:
    st.session_state.user = None
if "menu" not in st.session_state:
    st.session_state.menu = "Dashboard"


# ====== HELPERS GERAIS ======
def formatar_data_br(valor):
    if not valor:
        return ""
    try:
        return valor.strftime("%d/%m/%Y")
    except Exception:
        try:
            return pd.to_datetime(valor).strftime("%d/%m/%Y")
        except Exception:
            return str(valor)


def gerar_slots_horario():
    slots = []
    h, m = 7, 0
    while h < 20 or (h == 20 and m == 0):
        slots.append(f"{h:02d}:{m:02d}")
        m += 15
        if m >= 60:
            m = 0
            h += 1
    return slots


def calcular_hora_fim(hora_inicio: str, duracao_min: int) -> str:
    try:
        h, m = map(int, hora_inicio.split(":"))
        total = h * 60 + m + duracao_min
        return f"{total // 60:02d}:{total % 60:02d}"
    except Exception:
        return ""


# ── Calendário proporcional (estilo Google) ──────────────────────────────────
PX_PER_MIN = 1.5
CAL_START = 7 * 60   # 07:00 em minutos
CAL_END   = 20 * 60  # 20:00 em minutos
CAL_H     = int((CAL_END - CAL_START) * PX_PER_MIN)  # altura total em px


def _hora_min(hora_str: str) -> int:
    try:
        h, m = map(int, hora_str.split(":"))
        return h * 60 + m
    except Exception:
        return CAL_START


def _top_px(hora_str: str) -> int:
    return max(0, int((_hora_min(hora_str) - CAL_START) * PX_PER_MIN))


def _height_px(duracao_min: int) -> int:
    return max(22, int(duracao_min * PX_PER_MIN))


def _coluna_html(ags_dia: list, col_w: int) -> str:
    """Gera HTML de uma coluna de dia com cards proporcionais e sem duplicação."""
    ags = sorted(ags_dia, key=lambda a: a.hora_inicio)

    # Detecta sobreposições e distribui em sub-colunas
    col_ends: list = []
    col_idx: dict = {}
    for ag in ags:
        placed = False
        for ci, end in enumerate(col_ends):
            if ag.hora_inicio >= end:
                col_ends[ci] = ag.hora_fim
                col_idx[ag.id] = ci
                placed = True
                break
        if not placed:
            col_idx[ag.id] = len(col_ends)
            col_ends.append(ag.hora_fim)

    n_sub = max(col_idx.values()) + 1 if col_idx else 1
    card_w = max(40, (col_w - 4) // n_sub)

    # Linhas de hora (grid)
    html = ""
    for h in range(7, 21):
        top = _top_px(f"{h:02d}:00")
        html += (
            f'<div style="position:absolute;top:{top}px;left:0;right:0;'
            f'border-top:1px solid #e9ecef;pointer-events:none;"></div>'
        )

    # Cards de agendamento
    for ag in ags:
        top  = _top_px(ag.hora_inicio)
        h    = _height_px(ag.duracao_min)
        ci   = col_idx.get(ag.id, 0)
        left = ci * (card_w + 2)
        cor  = ag.cor_profissional or "#E3A5C7"
        icone = "✅" if ag.confirmado else "⏳"
        pacote_flag = " 📦" if getattr(ag, "_tem_pacote", False) else ""

        if h >= 80:
            sala_txt = f" · {ag.sala}" if getattr(ag, "sala", None) else ""
            inner = (
                f'<div style="font-size:11px;font-weight:700;overflow:hidden;'
                f'white-space:nowrap;text-overflow:ellipsis;">'
                f'{ag.cliente_nome or "Sem cliente"}</div>'
                f'<div style="font-size:10px;overflow:hidden;white-space:nowrap;'
                f'text-overflow:ellipsis;">{ag.procedimento or ""}{sala_txt}</div>'
                f'<div style="font-size:10px;color:rgba(0,0,0,0.55);">'
                f'{ag.hora_inicio}–{ag.hora_fim} {icone}{pacote_flag}</div>'
            )
        elif h >= 40:
            sala_txt = f" · {ag.sala}" if getattr(ag, "sala", None) else ""
            inner = (
                f'<div style="font-size:11px;font-weight:700;overflow:hidden;'
                f'white-space:nowrap;text-overflow:ellipsis;">'
                f'{ag.cliente_nome or "Sem cliente"}</div>'
                f'<div style="font-size:10px;overflow:hidden;white-space:nowrap;'
                f'text-overflow:ellipsis;">{ag.procedimento or ""}{sala_txt} {icone}{pacote_flag}</div>'
            )
        else:
            inner = (
                f'<div style="font-size:10px;overflow:hidden;white-space:nowrap;'
                f'text-overflow:ellipsis;">'
                f'{ag.cliente_nome or "Sem cliente"} {icone}{pacote_flag}</div>'
            )

        html += (
            f'<div style="position:absolute;top:{top+1}px;left:{left+1}px;'
            f'width:{card_w-3}px;height:{h-2}px;'
            f'background:{cor};border-radius:4px;padding:3px 6px;'
            f'overflow:hidden;z-index:2;'
            f'border-left:3px solid rgba(0,0,0,0.18);'
            f'box-shadow:0 1px 3px rgba(0,0,0,0.12);">'
            f'{inner}'
            f'</div>'
        )
    return html


def _render_calendario(dias: list, ags_por_dia: dict, semana: bool = False) -> str:
    """Monta o HTML completo do calendário proporcional."""
    TIME_W = 52
    n = len(dias)
    # Dia único: coluna ocupa tudo; semana: flex igual com mínimo
    col_flex = "flex:1;" if n == 1 else "flex:1;min-width:110px;"
    # Para _coluna_html precisamos de um col_w estimado (usado para calcular sub-colunas)
    col_w_est = 700 if n == 1 else 150

    # Eixo de horas
    eixo = ""
    for h in range(7, 21):
        top = _top_px(f"{h:02d}:00")
        eixo += (
            f'<div style="position:absolute;top:{top - 7}px;right:4px;'
            f'font-size:10px;color:#9ca3af;">{h:02d}:00</div>'
        )

    # Colunas de dias
    colunas = ""
    nomes_sem = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    hoje = _hoje()
    for dia in dias:
        ags = ags_por_dia.get(dia, [])
        col_html = _coluna_html(ags, col_w_est)

        cabecalho = ""
        if semana:
            bg  = "#E3A5C7" if dia == hoje else "#f3f4f6"
            clr = "#fff"    if dia == hoje else "#374151"
            cabecalho = (
                f'<div style="text-align:center;padding:5px 2px;'
                f'background:{bg};border-radius:6px 6px 0 0;'
                f'border-bottom:1px solid #e5e7eb;">'
                f'<span style="font-size:11px;font-weight:700;color:{clr};">'
                f'{nomes_sem[dia.weekday()]} {dia.day:02d}/{dia.month:02d}'
                f'</span></div>'
            )

        colunas += (
            f'<div style="{col_flex}border-left:1px solid #e5e7eb;overflow:hidden;">'
            f'{cabecalho}'
            f'<div style="position:relative;height:{CAL_H}px;">{col_html}</div>'
            f'</div>'
        )

    return (
        f'<div style="display:flex;width:100%;overflow-x:auto;border:1px solid #e5e7eb;'
        f'border-radius:8px;background:#fff;font-family:sans-serif;">'
        f'<div style="width:{TIME_W}px;flex-shrink:0;position:relative;'
        f'height:{CAL_H}px;border-right:1px solid #e5e7eb;background:#f9fafb;">'
        f'{eixo}</div>'
        f'{colunas}'
        f'</div>'
    )


def _mostrar_pdf(pdf_bytes, nome_arquivo, key_suffix=""):
    """PDF com botão de compartilhar nativo (iOS/Android) + download fallback"""
    import base64
    b64 = base64.b64encode(pdf_bytes).decode()
    st.markdown(f'''
    <script>
    async function compartilharPDF_{key_suffix.replace("-","_")}() {{
        try {{
            const b64 = "{b64}";
            const byteChars = atob(b64);
            const byteArray = new Uint8Array(byteChars.length);
            for (let i = 0; i < byteChars.length; i++) byteArray[i] = byteChars.charCodeAt(i);
            const file = new File([byteArray], "{nome_arquivo}", {{type: "application/pdf"}});
            if (navigator.canShare && navigator.canShare({{files: [file]}})) {{
                await navigator.share({{files: [file], title: "{nome_arquivo}"}});
            }} else {{
                // Fallback: download direto
                const link = document.createElement("a");
                link.href = "data:application/pdf;base64," + b64;
                link.download = "{nome_arquivo}";
                link.click();
            }}
        }} catch(e) {{
            if (e.name !== "AbortError") {{
                const link = document.createElement("a");
                link.href = "data:application/pdf;base64,{b64}";
                link.download = "{nome_arquivo}";
                link.click();
            }}
        }}
    }}
    </script>
    <button onclick="compartilharPDF_{key_suffix.replace("-","_")}()" style="
        width:100%;padding:12px;margin:8px 0;
        background:#d59c9c;color:white;border:none;border-radius:8px;
        font-size:1em;font-weight:600;cursor:pointer;">
        📤 Compartilhar / Baixar: {nome_arquivo}
    </button>
    ''', unsafe_allow_html=True)


# ====== LOGIN ======
def login_screen():
    # Espaço superior
    st.markdown("<div style='padding-top:2.5rem'></div>", unsafe_allow_html=True)

    # Logo centralizada
    col_l, col_c, col_r = st.columns([1, 1.4, 1])
    with col_c:
        try:
            st.image("ui/logogf.png", use_container_width=True)
        except Exception:
            st.markdown(
                "<h2 style='text-align:center;font-family:Cormorant Garamond,serif;color:#b87575'>Gabriela Franco</h2>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

        # Linha divisória sutil
        st.markdown(
            "<hr style='border:none;border-top:1px solid #f0d5ce;margin:0 0 1.4rem 0'>",
            unsafe_allow_html=True,
        )

        # Form com autocomplete para iPhone salvar credenciais
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("E-mail", key="login_email", autocomplete="username")
            senha = st.text_input("Senha", type="password", key="login_senha", autocomplete="current-password")
            entrar = st.form_submit_button("Entrar", use_container_width=True)
        if entrar:
            user = authenticate(email, senha)
            if user:
                st.session_state.user = {"id": user.id, "nome": user.nome, "perfil": user.perfil}
                st.success(f"Bem-vinda, {user.nome}!")
                st.rerun()
            else:
                st.error("Credenciais inválidas.")


def require_login():
    if not st.session_state.user:
        login_screen()
        st.stop()


# ====== HELPERS DE CLIENTE ======
def inicializar_state_cliente():
    defaults = {
        "cliente_id_edicao": 0,
        "cliente_edicao_habilitada": False,
        "cadastro_busca": "",
        "cadastro_cliente_id": 0,
        "ficha_busca": "",
        "ficha_cliente_id": 0,
        "cliente_nome": "",
        "cliente_cpf": "",
        "cliente_data_nasc": date(2000, 1, 1),
        "cliente_telefone": "",
        "cliente_email": "",
        "cliente_profissao": "",
        "cliente_endereco": "",
        "cliente_bairro": "",
        "cliente_cidade": "",
        "cliente_peso": 0.0,
        "cliente_altura": 0.0,
        "cliente_exames": "",
        "cliente_func_int": "",
        "cliente_uso_vit": "",
        "cliente_marcacao": "",
        "cliente_neoplasia": False,
        "cliente_epilepsia": False,
        "cliente_outras": "",
        "cliente_queixa": "",
        "cliente_termo": False,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def limpar_form_cliente():
    st.session_state["cliente_id_edicao"] = 0
    st.session_state["cliente_edicao_habilitada"] = False
    st.session_state["cadastro_busca"] = ""
    st.session_state["cadastro_cliente_id"] = 0
    st.session_state["ficha_busca"] = ""
    st.session_state["ficha_cliente_id"] = 0
    st.session_state["cliente_nome"] = ""
    st.session_state["cliente_cpf"] = ""
    st.session_state["cliente_data_nasc"] = date(2000, 1, 1)
    st.session_state["cliente_telefone"] = ""
    st.session_state["cliente_email"] = ""
    st.session_state["cliente_profissao"] = ""
    st.session_state["cliente_endereco"] = ""
    st.session_state["cliente_bairro"] = ""
    st.session_state["cliente_cidade"] = ""
    st.session_state["cliente_peso"] = 0.0
    st.session_state["cliente_altura"] = 0.0
    st.session_state["cliente_exames"] = ""
    st.session_state["cliente_func_int"] = ""
    st.session_state["cliente_uso_vit"] = ""
    st.session_state["cliente_marcacao"] = ""
    st.session_state["cliente_neoplasia"] = False
    st.session_state["cliente_epilepsia"] = False
    st.session_state["cliente_outras"] = ""
    st.session_state["cliente_queixa"] = ""
    st.session_state["cliente_termo"] = False


def carregar_cliente_no_form(cliente: Client):
    st.session_state["cliente_id_edicao"] = cliente.id
    st.session_state["cliente_edicao_habilitada"] = False
    st.session_state["cadastro_cliente_id"] = cliente.id
    st.session_state["cliente_nome"] = cliente.nome or ""
    st.session_state["cliente_cpf"] = cliente.cpf or ""
    st.session_state["cliente_data_nasc"] = cliente.data_nascimento or date(2000, 1, 1)
    st.session_state["cliente_telefone"] = cliente.telefone or ""
    st.session_state["cliente_email"] = cliente.email or ""
    st.session_state["cliente_profissao"] = cliente.profissao or ""
    st.session_state["cliente_endereco"] = cliente.endereco or ""
    st.session_state["cliente_bairro"] = cliente.bairro or ""
    st.session_state["cliente_cidade"] = cliente.cidade or ""
    st.session_state["cliente_peso"] = float(cliente.peso or 0.0)
    st.session_state["cliente_altura"] = float(cliente.altura or 0.0)
    st.session_state["cliente_exames"] = cliente.exames_recentes or ""
    st.session_state["cliente_func_int"] = cliente.funcionamento_intestinal or ""
    st.session_state["cliente_uso_vit"] = cliente.uso_vitaminas or ""
    st.session_state["cliente_marcacao"] = cliente.marcacao_corporal or ""
    st.session_state["cliente_neoplasia"] = bool(cliente.neoplasia)
    st.session_state["cliente_epilepsia"] = bool(cliente.epilepsia)
    st.session_state["cliente_outras"] = cliente.outras_condicoes or ""
    st.session_state["cliente_queixa"] = cliente.queixa_principal or ""
    st.session_state["cliente_termo"] = bool(cliente.termo_aceite)


def buscar_clientes(db, termo):
    termo = (termo or "").strip()
    if not termo:
        return []
    like = f"%{termo}%"
    return (
        db.query(Client)
        .filter(
            (Client.nome.like(like)) |
            (Client.cpf.like(like)) |
            (Client.telefone.like(like)) |
            (Client.email.like(like))
        )
        .order_by(Client.nome.asc())
        .limit(20)
        .all()
    )


def render_sugestoes_cliente(db, termo, contexto="cadastro"):
    def buscar_opcoes(searchterm: str):
        resultados = buscar_clientes(db, searchterm)
        return [
            f"{c.nome} | CPF: {c.cpf or '-'} | Tel: {c.telefone or '-'}"
            for c in resultados
        ]

    selecionado = st_searchbox(
        search_function=buscar_opcoes,
        label="Digite nome, CPF, telefone ou e-mail",
        placeholder="Ex.: Amanda",
        key=f"{contexto}_searchbox",
        clear_on_submit=False,
        default=None,
    )

    if not selecionado:
        return

    cliente_escolhido = None
    resultados = buscar_clientes(db, selecionado)
    for c in resultados:
        rotulo = f"{c.nome} | CPF: {c.cpf or '-'} | Tel: {c.telefone or '-'}"
        if rotulo == selecionado:
            cliente_escolhido = c
            break

    if not cliente_escolhido:
        nome_base = str(selecionado).split("|")[0].strip()
        if nome_base:
            cliente_escolhido = (
                db.query(Client)
                .filter(Client.nome.like(f"%{nome_base}%"))
                .order_by(Client.nome.asc())
                .first()
            )

    if not cliente_escolhido:
        return

    if contexto == "cadastro":
        if st.session_state.get("cadastro_cliente_id") != cliente_escolhido.id:
            carregar_cliente_no_form(cliente_escolhido)
            st.session_state["cadastro_cliente_id"] = cliente_escolhido.id
            st.rerun()
    elif contexto == "ficha":
        if st.session_state.get("ficha_cliente_id") != cliente_escolhido.id:
            st.session_state["ficha_cliente_id"] = cliente_escolhido.id
            st.rerun()


def botao_toggle_edicao():
    ligado = st.session_state.get("cliente_edicao_habilitada", False)
    texto = "✏️ Edição habilitada" if ligado else "👁️ Somente visualização"
    if st.button(texto, use_container_width=True, key="botao_toggle_edicao"):
        # Apenas alterna o flag, não limpa os dados
        st.session_state["cliente_edicao_habilitada"] = not ligado
        st.rerun()


# ====== MENU LATERAL ======
def sidebar_menu():
    user = st.session_state.user
    with st.sidebar:
        # Logo / cabeçalho da sidebar
        st.markdown(
            "<div style='background:#fff0ee;padding:1rem 0.8rem 0.5rem 0.8rem;border-bottom:1px solid #f0d5ce;'>",
            unsafe_allow_html=True,
        )
        try:
            st.image("ui/logogf.png", use_container_width=True)
        except Exception:
            st.markdown(
                "<p style='text-align:center;font-family:Cormorant Garamond,serif;color:#b87575;font-weight:700;margin:0'>Gabriela Franco</p>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        # Grupos de menu
        # Define grupos base por perfil
        perfil = user.get("perfil", "") if user else ""
        
        grupos = {
            "Principal": [
                ("🏠", "Dashboard", "Dashboard"),
                ("📅", "Agenda", "Agenda"),
            ],
            "Clientes": [
                ("👤", "Clientes", "Clientes"),
                ("📋", "Pré-avaliação / Consulta", "Pré-avaliação"),
                ("📏", "Biometria", "Biometria"),
                ("🩺", "Atendimentos", "Atendimentos"),
            ],
        }
        
        # Gestão - varia por perfil
        gestao_itens = []
        
        if perfil == "admin":
            # Admin vê tudo
            gestao_itens = [
                ("💳", "Vendas", "Vendas"),
                ("📦", "Estoque", "Estoque"),
                ("📊", "Relatórios", "Relatórios"),
                ("📝", "Contratos", "Contratos"),
                ("🗂️", "Cadastros", "Cadastros"),
                ("⚙️", "Usuários", "Usuários"),
            ]
        elif perfil == "recepcao":
            # Recepção não vê Relatórios
            gestao_itens = [
                ("💳", "Vendas", "Vendas"),
                ("📦", "Estoque", "Estoque"),
                ("📝", "Contratos", "Contratos"),
                ("🗂️", "Cadastros", "Cadastros"),
            ]
        elif perfil == "profissional":
            # Profissional não vê Vendas, Relatórios, Cadastros
            gestao_itens = [
                ("📦", "Estoque", "Estoque"),
                ("📝", "Contratos", "Contratos"),
            ]
        else:
            # Padrão (sem perfil definido) - acesso mínimo
            gestao_itens = [
                ("📦", "Estoque", "Estoque"),
                ("📝", "Contratos", "Contratos"),
            ]
        
        if gestao_itens:
            grupos["Gestão"] = gestao_itens

        for secao, itens in grupos.items():
            st.markdown(f'<div class="gf-sidebar-section">{secao}</div>', unsafe_allow_html=True)
            for icone, label, rota in itens:
                ativo = st.session_state.menu == rota
                tipo = "primary" if ativo else "secondary"
                prefixo = f"{icone} " if icone else ""
                if st.button(f"{prefixo}{label}", key=f"nav_{rota}", type=tipo, use_container_width=True):
                    st.session_state.menu = rota
                    st.rerun()

        st.markdown("---")
        nome_usuario = user["nome"] if user else ""
        perfil_usuario = user.get("perfil", "") if user else ""
        st.markdown(f"""
        <div style="font-family:'DM Sans',sans-serif;font-size:0.82rem;color:#9e7575;padding:0.4rem 0.5rem;">
            Logada como: <strong style="color:#b87575">{nome_usuario}</strong><br>
            <span style="font-size:0.75rem;opacity:0.75">{perfil_usuario}</span>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Sair", type="secondary", use_container_width=True):
            st.session_state.user = None
            st.rerun()


# ====== TELA: DASHBOARD ======
def tela_dashboard():
    header_titulo("ACOMPANHAMENTO GERAL", "Visão geral da clínica")
    db = SessionLocal()
    try:
        _data_hoje = _hoje()
        _ini_mes = _data_hoje.replace(day=1)
        from datetime import timedelta
        
        # Cards atualizados
        total_clientes = db.query(Client).count()
        
        # Atendimentos no mês
        atendimentos_mes = db.query(Appointment).filter(
            Appointment.data >= _ini_mes,
            Appointment.data <= _data_hoje
        ).count()
        
        # Agendamentos totais (todos os futuros e passados do mês)
        agendamentos_total = db.query(ScheduledAppointment).filter(
            ScheduledAppointment.data >= _ini_mes
        ).count()
        
        # Atendimentos hoje
        atendimentos_hoje = db.query(Appointment).filter(
            Appointment.data == _data_hoje
        ).count()
        
        # Agendamentos cancelados/excluídos (busca no log por acao='excluido' no mês)
        try:
            cancelados_mes = db.query(AgendaLog).filter(
                AgendaLog.acao == 'excluido',
                AgendaLog.criado_em >= _ini_mes
            ).count()
        except:
            cancelados_mes = 0
        
        # Produtos com vencimento crítico (próximos 30 dias)
        try:
            data_critica = _data_hoje + timedelta(days=30)
            produtos_vencimento_critico = db.query(StockLote).filter(
                StockLote.data_validade <= data_critica,
                StockLote.data_validade >= _data_hoje
            ).count()
        except:
            produtos_vencimento_critico = 0

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total de clientes", total_clientes)
        c2.metric("Atendimentos no mês", atendimentos_mes)
        c3.metric("Agendamentos totais", agendamentos_total)
        c4.metric("Atendimentos hoje", atendimentos_hoje)
        c5.metric("Agend. cancelados", cancelados_mes)
        c6.metric("Vencimento crítico", produtos_vencimento_critico)

        st.markdown("---")

        # --- A confirmar AMANHÃ ---
        _amanha = _data_hoje + timedelta(days=1)
        st.markdown("### Clientes a confirmar (amanhã)")
        pendentes = (
            db.query(ScheduledAppointment)
            .filter(
                ScheduledAppointment.data == _amanha,
                ScheduledAppointment.confirmado == False,
            )
            .order_by(ScheduledAppointment.hora_inicio.asc())
            .all()
        )

        if "confirmados_dash" not in st.session_state:
            st.session_state["confirmados_dash"] = set()

        if pendentes:
            for ag in pendentes:
                if ag.id in st.session_state["confirmados_dash"]:
                    continue
                col_info, col_check = st.columns([5, 1])
                with col_info:
                    st.write(
                        f"**{ag.hora_inicio}** — {ag.cliente_nome or 'N/A'} | "
                        f"{ag.procedimento or ''} | {ag.profissional}"
                    )
                with col_check:
                    if st.checkbox("Confirmar", key=f"conf_{ag.id}"):
                        ag.confirmado = True
                        db.commit()
                        st.session_state["confirmados_dash"].add(ag.id)
                        st.rerun()
        else:
            st.info("Nenhum agendamento pendente de confirmação para amanhã.")

        st.markdown("---")

        # --- Confirmados HOJE ---
        st.markdown("### Confirmados hoje")
        confirmados = (
            db.query(ScheduledAppointment)
            .filter(
                ScheduledAppointment.data == _data_hoje,
                ScheduledAppointment.confirmado == True,
            )
            .order_by(ScheduledAppointment.hora_inicio.asc())
            .all()
        )
        if confirmados:
            dados_conf = [
                {
                    "Hora": ag.hora_inicio,
                    "Cliente": ag.cliente_nome or "",
                    "Procedimento": ag.procedimento or "",
                    "Profissional": ag.profissional,
                }
                for ag in confirmados
            ]
            st.dataframe(pd.DataFrame(dados_conf), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum atendimento confirmado ainda hoje.")

        st.markdown("---")

        # --- Gráfico por procedimento (MÊS VIGENTE) ---
        st.markdown("### Atendimentos por procedimento (mês vigente)")
        df_at = pd.read_sql(
            db.query(Appointment).filter(
                Appointment.data >= _ini_mes,
                Appointment.data <= _data_hoje
            ).statement, db.bind
        )
        if not df_at.empty and "tipo_tratamento" in df_at.columns:
            df_at["tipo_tratamento"] = df_at["tipo_tratamento"].fillna("Não informado")
            por_proc = (
                df_at.groupby("tipo_tratamento")["id"]
                .count()
                .reset_index()
                .rename(columns={"id": "total", "tipo_tratamento": "Procedimento"})
                .sort_values("total", ascending=False)
            )
            chart = (
                alt.Chart(por_proc)
                .mark_bar()
                .encode(
                    x=alt.X("total:Q", title="Atendimentos"),
                    y=alt.Y("Procedimento:N", sort="-x"),
                    color=alt.Color("Procedimento:N", legend=None),
                )
                .properties(height=300)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("Nenhum atendimento registrado no mês vigente.")

    except Exception as e:
        st.warning(f"Não foi possível carregar todos os dados: {e}")
    finally:
        db.close()


# ====== TELA: AGENDA ======
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


def _init_agenda_state():
    defaults = {
        "ag_edit_id": None,
        "ag_cliente": "— selecione —",
        "ag_prof": "— selecione —",
        "ag_proc": "",
        "ag_data": _hoje(),
        "ag_hora_ini": "08:00",
        "ag_duracao": 60,
        "ag_obs": "",
        "ag_sala": "— selecione —",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def tela_agenda():
    from collections import defaultdict

    header_titulo("🕐 Agenda", "Agendamentos e calendário diário")
    _init_agenda_state()

    # Aplica pending edit ANTES de qualquer widget ser renderizado
    if "ag_pending_edit" in st.session_state:
        for k, v in st.session_state.pop("ag_pending_edit").items():
            st.session_state[k] = v

    db = SessionLocal()
    try:
        slots = gerar_slots_horario()
        duracoes = [15, 30, 45, 60, 75, 90, 105, 120]

        profs_db = db.query(Professional).order_by(Professional.nome.asc()).all()
        nomes_prof = [p.nome for p in profs_db]
        cor_por_prof = {p.nome: (p.cor or "#E3A5C7") for p in profs_db}
        clientes = db.query(Client).order_by(Client.nome.asc()).all()
        mapa_cli = {f"{c.nome} ({c.cpf or ''})": (c.id, c.nome) for c in clientes}
        opcoes_cli = ["— selecione —"] + list(mapa_cli.keys())

        modo_edicao = st.session_state["ag_edit_id"] is not None
        ag_edit = db.get(ScheduledAppointment, st.session_state["ag_edit_id"]) if modo_edicao else None

        # ── Formulário ──────────────────────────────────────────────────────
        st.markdown("### Agendamento")

        aba_clientes_ag, aba_salas_ag = st.tabs(["👤 Clientes", "🚪 Salas"])

        # ════════════════════════════════════════════
        # SUB-ABA: CLIENTES
        # ════════════════════════════════════════════
        with aba_clientes_ag:
            if modo_edicao and ag_edit:
                st.info(f"Editando: **{ag_edit.cliente_nome or 'N/A'}** — {ag_edit.hora_inicio}–{ag_edit.hora_fim}")
                if st.button("✖ Cancelar edição", key="ag_cancel"):
                    for k in ["ag_edit_id","ag_cliente","ag_prof","ag_proc",
                               "ag_hora_ini","ag_duracao","ag_obs","ag_sala","ag_data"]:
                        st.session_state.pop(k, None)
                    st.rerun()

            OPCOES_SALA = ["— selecione —", "Sala 1", "Sala 2", "Sala 3", "Sala 4", "Sala 5", "Soroterapia"]

            col1, col2 = st.columns(2)
            with col1:
                if st.session_state.get("ag_cliente") not in opcoes_cli:
                    st.session_state["ag_cliente"] = "— selecione —"
                cliente_sel = st.selectbox("Cliente", opcoes_cli, key="ag_cliente")

                # ── Pacotes disponíveis (checkboxes) ──
                if cliente_sel and cliente_sel != "— selecione —":
                    _cli_id_ag = mapa_cli.get(cliente_sel, (0, ""))[0]
                    if _cli_id_ag:
                        try:
                            from models.sale import Sale, SaleItem
                            _pacotes = (
                                db.query(SaleItem)
                                .join(Sale)
                                .filter(
                                    Sale.cliente_id == _cli_id_ag,
                                    SaleItem.tipo == "pacote",
                                    SaleItem.sessoes_usadas < SaleItem.sessoes_total,
                                ).all()
                            )
                            if _pacotes:
                                st.caption("📦 Pacotes ativos — selecione para vincular ao agendamento:")
                                pacote_selecionado_id = st.session_state.get("ag_pacote_item_id")
                                for _p in _pacotes:
                                    rest = _p.sessoes_total - _p.sessoes_usadas
                                    chave = f"pkg_{_p.id}"
                                    marcado = st.checkbox(
                                        f"📦 {_p.procedimento} — {rest} sessão(ões) restante(s)",
                                        key=chave,
                                        value=(pacote_selecionado_id == _p.id),
                                    )
                                    if marcado and pacote_selecionado_id != _p.id:
                                        st.session_state["ag_pacote_item_id"] = _p.id
                                        st.session_state["ag_proc"] = _p.procedimento
                                        st.rerun()
                                    elif not marcado and pacote_selecionado_id == _p.id:
                                        st.session_state["ag_pacote_item_id"] = None
                                        st.session_state["ag_proc"] = ""
                                        st.rerun()
                            else:
                                st.caption("Sem pacotes ativos para esta cliente.")
                        except Exception:
                            pass

                data_ag = st.date_input("Data", format="DD/MM/YYYY", key="ag_data")

                if nomes_prof:
                    opcoes_prof = ["— selecione —"] + nomes_prof
                    if st.session_state.get("ag_prof") not in opcoes_prof:
                        st.session_state["ag_prof"] = "— selecione —"
                    prof_sel = st.selectbox("Profissional responsável*", opcoes_prof, key="ag_prof")
                else:
                    st.info("Cadastre um profissional abaixo primeiro.")
                    prof_sel = "— selecione —"

                procedimento = st.text_input("Procedimento", key="ag_proc")

                if st.session_state.get("ag_sala") not in OPCOES_SALA:
                    st.session_state["ag_sala"] = "— selecione —"
                sala_sel = st.selectbox("Sala", OPCOES_SALA, key="ag_sala")

            with col2:
                if st.session_state.get("ag_hora_ini") not in slots:
                    st.session_state["ag_hora_ini"] = "08:00"
                hora_inicio = st.selectbox("Hora início", slots, key="ag_hora_ini")

                if st.session_state.get("ag_duracao") not in duracoes:
                    st.session_state["ag_duracao"] = 60
                duracao = st.selectbox("Duração (min)", duracoes, key="ag_duracao")

                # Calcula hora fim e exibe em tempo real
                hora_fim_calc = calcular_hora_fim(hora_inicio, duracao)
                st.markdown(f"**Hora fim:** {hora_fim_calc}")
                observacoes_ag = st.text_area("Observações", key="ag_obs", height=150)

                # Recorrência
                if not modo_edicao:
                    recorrente = st.checkbox("Recorrência", key="ag_recorrente")
                    if recorrente:
                        tipo_recorrencia = st.selectbox(
                            "Tipo de recorrência",
                            ["Semanal", "Quinzenal", "Mensal", "Bimestral", "Trimestral", "Semestral"],
                            key="ag_tipo_recorrencia"
                        )
                        num_repeticoes = st.number_input("Quantas vezes?", min_value=2, max_value=52, value=4, step=1, key="ag_num_repeticoes")
                    else:
                        tipo_recorrencia = None
                        num_repeticoes = 1
                else:
                    recorrente = False
                    tipo_recorrencia = None
                    num_repeticoes = 1

            btn_label = "💾 Salvar alterações" if modo_edicao else "💾 Salvar agendamento"
            if st.button(btn_label, use_container_width=True, key="ag_salvar"):
                if prof_sel == "— selecione —":
                    st.error("Selecione um profissional.")
                else:
                    cli_id, cli_nome = None, None
                    if cliente_sel != "— selecione —" and cliente_sel in mapa_cli:
                        cli_id, cli_nome = mapa_cli[cliente_sel]
                    sala_val = sala_sel if sala_sel != "— selecione —" else None

                    if modo_edicao and ag_edit:
                        _antes = __import__("json").dumps({
                            "data": str(ag_edit.data), "hora_inicio": ag_edit.hora_inicio,
                            "hora_fim": ag_edit.hora_fim, "cliente": ag_edit.cliente_nome,
                            "profissional": ag_edit.profissional, "procedimento": ag_edit.procedimento,
                            "sala": ag_edit.sala,
                        }, ensure_ascii=False)
                        ag_edit.data = data_ag
                        ag_edit.hora_inicio = hora_inicio
                        ag_edit.hora_fim = hora_fim_calc
                        ag_edit.duracao_min = duracao
                        ag_edit.cliente_id = cli_id
                        ag_edit.cliente_nome = cli_nome
                        ag_edit.profissional = prof_sel
                        ag_edit.procedimento = procedimento.strip()
                        ag_edit.observacoes = observacoes_ag
                        ag_edit.sala = sala_val
                        ag_edit.cor_profissional = cor_por_prof.get(prof_sel, "#E3A5C7")
                        db.commit()
                        try:
                            _ulog = st.session_state.get("user", {})
                            db.add(AgendaLog(
                                agendamento_id=ag_edit.id,
                                acao="editado",
                                usuario_id=_ulog.get("id"),
                                usuario_nome=_ulog.get("nome", ""),
                                dados_antes=_antes,
                                dados_depois=__import__("json").dumps({
                                    "data": str(ag_edit.data), "hora_inicio": ag_edit.hora_inicio,
                                    "hora_fim": ag_edit.hora_fim, "cliente": ag_edit.cliente_nome,
                                    "profissional": ag_edit.profissional, "procedimento": ag_edit.procedimento,
                                    "sala": ag_edit.sala,
                                }, ensure_ascii=False),
                            ))
                            db.commit()
                        except Exception:
                            pass
                        for k in ["ag_edit_id","ag_cliente","ag_prof","ag_proc",
                                   "ag_hora_ini","ag_duracao","ag_obs","ag_sala","ag_data"]:
                            st.session_state.pop(k, None)
                        st.success("Agendamento atualizado!")
                    else:
                        _pacote_item_id = st.session_state.pop("ag_pacote_item_id", None)
                        # Criar agendamentos (1 ou múltiplos se recorrente)
                        for _rep_i in range(int(num_repeticoes)):
                            # Calcular data baseada no tipo de recorrência
                            if tipo_recorrencia == "Semanal":
                                _data_sem = data_ag + timedelta(weeks=_rep_i)
                            elif tipo_recorrencia == "Quinzenal":
                                _data_sem = data_ag + timedelta(weeks=_rep_i * 2)
                            elif tipo_recorrencia == "Mensal":
                                _data_sem = data_ag + timedelta(days=_rep_i * 30)
                            elif tipo_recorrencia == "Bimestral":
                                _data_sem = data_ag + timedelta(days=_rep_i * 60)
                            elif tipo_recorrencia == "Trimestral":
                                _data_sem = data_ag + timedelta(days=_rep_i * 90)
                            elif tipo_recorrencia == "Semestral":
                                _data_sem = data_ag + timedelta(days=_rep_i * 180)
                            else:
                                _data_sem = data_ag + timedelta(weeks=_rep_i)
                            
                            # Pular sábado (5) e domingo (6)
                            while _data_sem.weekday() >= 5:
                                _data_sem = _data_sem + timedelta(days=1)
                            novo = ScheduledAppointment(
                                data=_data_sem,
                                hora_inicio=hora_inicio,
                                hora_fim=hora_fim_calc,
                                duracao_min=duracao,
                                cliente_id=cli_id,
                                cliente_nome=cli_nome,
                                profissional=prof_sel,
                                procedimento=procedimento.strip(),
                                observacoes=observacoes_ag,
                                confirmado=False,
                                sala=sala_val,
                                cor_profissional=cor_por_prof.get(prof_sel, "#E3A5C7"),
                            )
                            db.add(novo)
                            db.flush()
                            if _pacote_item_id and hasattr(novo, "sale_item_id") and _sem_i == 0:
                                novo.sale_item_id = _pacote_item_id
                            try:
                                _ulog = st.session_state.get("user", {})
                                db.add(AgendaLog(
                                    agendamento_id=novo.id,
                                    acao="criado",
                                    usuario_id=_ulog.get("id"),
                                    usuario_nome=_ulog.get("nome", ""),
                                    dados_depois=__import__("json").dumps({
                                        "data": str(novo.data), "hora_inicio": novo.hora_inicio,
                                        "hora_fim": novo.hora_fim, "cliente": novo.cliente_nome,
                                        "profissional": novo.profissional, "procedimento": novo.procedimento,
                                        "sala": novo.sala, "duracao_min": novo.duracao_min,
                                    }, ensure_ascii=False),
                                ))
                            except Exception:
                                pass
                        db.commit()
                        if int(num_semanas) > 1:
                            st.success(f"{int(num_semanas)} agendamentos criados (recorrência semanal)!")
                        else:
                            st.success("Agendamento salvo!")
                        for _k in ["ag_cliente","ag_prof","ag_proc","ag_hora_ini",
                                    "ag_duracao","ag_obs","ag_sala","ag_data",
                                    "ag_pacote_item_id","ag_recorrente","ag_num_semanas"]:
                            st.session_state.pop(_k, None)
                    st.rerun()

        # ════════════════════════════════════════════
        # SUB-ABA: SALAS
        # ════════════════════════════════════════════
        with aba_salas_ag:
            OPCOES_SALA_S = ["— selecione —", "Sala 1", "Sala 2", "Sala 3", "Sala 4", "Sala 5", "Soroterapia"]
            _COR_SALA = "#a0c4e8"  # Cor padrão para reservas de sala
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                _responsavel_s = st.text_input("Nome do responsável", key="sala_responsavel")
                if st.session_state.get("sala_sala") not in OPCOES_SALA_S:
                    st.session_state["sala_sala"] = "— selecione —"
                _sala_s = st.selectbox("Sala", OPCOES_SALA_S, key="sala_sala")
                _data_s = st.date_input("Data", format="DD/MM/YYYY", key="sala_data")
                if nomes_prof:
                    _opcoes_prof_s = ["— selecione —"] + nomes_prof
                    if st.session_state.get("sala_prof") not in _opcoes_prof_s:
                        st.session_state["sala_prof"] = "— selecione —"
                    _prof_s = st.selectbox("Profissional (opcional)", _opcoes_prof_s, key="sala_prof")
                else:
                    _prof_s = "— selecione —"
            with col_s2:
                if st.session_state.get("sala_hora_ini") not in slots:
                    st.session_state["sala_hora_ini"] = "08:00"
                _hora_ini_s = st.selectbox("Hora início", slots, key="sala_hora_ini")
                if st.session_state.get("sala_duracao") not in duracoes:
                    st.session_state["sala_duracao"] = 60
                _duracao_s = st.selectbox("Duração (min)", duracoes, key="sala_duracao")
                # Calcula hora fim e exibe em tempo real
                _hora_fim_s = calcular_hora_fim(_hora_ini_s or "08:00", _duracao_s or 60)
                st.markdown(f"**Hora fim:** {_hora_fim_s}")
                _obs_s = st.text_area("Observações", key="sala_obs", height=80)

            if st.button("💾 Salvar reserva de sala", use_container_width=True, key="sala_salvar"):
                if not _responsavel_s or _sala_s == "— selecione —":
                    st.error("Informe o responsável e a sala.")
                else:
                    _prof_sala = _responsavel_s if _prof_s == "— selecione —" else _prof_s
                    _cor_sala = cor_por_prof.get(_prof_sala, _COR_SALA)
                    _novo_sala = ScheduledAppointment(
                        data=_data_s,
                        hora_inicio=_hora_ini_s,
                        hora_fim=_hora_fim_s,
                        duracao_min=_duracao_s,
                        cliente_id=None,
                        cliente_nome=f"[Sala] {_responsavel_s}",
                        profissional=_prof_sala,
                        procedimento=f"Reserva",
                        observacoes=_obs_s,
                        confirmado=False,
                        sala=_sala_s,
                        cor_profissional=_cor_sala,
                    )
                    db.add(_novo_sala)
                    db.commit()
                    try:
                        _ulog = st.session_state.get("user", {})
                        db.add(AgendaLog(
                            agendamento_id=_novo_sala.id,
                            acao="criado",
                            usuario_id=_ulog.get("id"),
                            usuario_nome=_ulog.get("nome", ""),
                            dados_depois=__import__("json").dumps({
                                "data": str(_data_s), "hora_inicio": _hora_ini_s,
                                "hora_fim": _hora_fim_s, "cliente": f"[Sala] {_responsavel_s}",
                                "profissional": _prof_sala, "sala": _sala_s,
                            }, ensure_ascii=False),
                        ))
                        db.commit()
                    except Exception:
                        pass
                    st.success("Reserva de sala salva!")
                    for _k in ["sala_responsavel","sala_sala","sala_hora_ini",
                                "sala_duracao","sala_obs","sala_data","sala_prof"]:
                        st.session_state.pop(_k, None)
                    st.rerun()

        st.markdown("---")

        # ── Controles do calendário ─────────────────────────────────────────
        ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([1, 1, 1, 1])
        with ctrl1:
            vista = st.radio("Visualizar", ["Dia", "Semana", "Mês"], horizontal=True, key="ag_vista")

        if vista == "Dia":
            with ctrl2:
                data_ref = st.date_input("Data", value=_hoje(), format="DD/MM/YYYY", key="ag_data_ref")
            dias = [data_ref]
        elif vista == "Semana":
            with ctrl2:
                data_ref = st.date_input("Qualquer data da semana", value=_hoje(),
                                         format="DD/MM/YYYY", key="ag_data_ref")
            monday = data_ref - timedelta(days=data_ref.weekday())
            sunday = monday + timedelta(days=6)
            with ctrl3:
                st.date_input("Início (Seg)", value=monday, format="DD/MM/YYYY",
                              disabled=True, key="ag_sem_ini")
            with ctrl4:
                st.date_input("Fim (Dom)", value=sunday, format="DD/MM/YYYY",
                              disabled=True, key="ag_sem_fim")
            dias = [monday + timedelta(days=i) for i in range(7)]
        else:  # Mês
            with ctrl2:
                data_ref = st.date_input("Qualquer data do mês", value=_hoje(),
                                         format="DD/MM/YYYY", key="ag_data_ref")
            import calendar
            primeiro_dia_mes = data_ref.replace(day=1)
            _, dias_no_mes = calendar.monthrange(data_ref.year, data_ref.month)
            ultimo_dia_mes = data_ref.replace(day=dias_no_mes)
            # Começa na segunda da primeira semana
            inicio_cal = primeiro_dia_mes - timedelta(days=primeiro_dia_mes.weekday())
            # Termina no domingo da última semana
            fim_cal = ultimo_dia_mes + timedelta(days=(6 - ultimo_dia_mes.weekday()))
            dias = [inicio_cal + timedelta(days=i) for i in range((fim_cal - inicio_cal).days + 1)]

        # Filtro por profissional
        col_filt, _ = st.columns([1, 3])
        with col_filt:
            opcoes_filt = ["Todos"] + nomes_prof
            filtro_prof = st.selectbox("Profissional (filtrar)", opcoes_filt,
                                       key="ag_filtro_prof", label_visibility="visible")

        ags_periodo_raw = (
            db.query(ScheduledAppointment)
            .filter(
                ScheduledAppointment.data >= dias[0],
                ScheduledAppointment.data <= dias[-1],
            )
            .order_by(ScheduledAppointment.hora_inicio.asc())
            .all()
        )
        # Aplica filtro de profissional
        ags_periodo = (
            ags_periodo_raw if filtro_prof == "Todos"
            else [ag for ag in ags_periodo_raw if ag.profissional == filtro_prof]
        )

        ags_por_dia: dict = defaultdict(list)
        for ag in ags_periodo:
            ags_por_dia[ag.data].append(ag)

        # Marcar quais agendamentos têm pacote ativo
        try:
            from models.sale import Sale, SaleItem
            for ag in ags_periodo:
                ag._tem_pacote = False
                if ag.cliente_id:
                    _pac = (
                        db.query(SaleItem)
                        .join(Sale)
                        .filter(
                            Sale.cliente_id == ag.cliente_id,
                            SaleItem.tipo == "pacote",
                            SaleItem.sessoes_usadas < SaleItem.sessoes_total,
                        ).first()
                    )
                    if _pac:
                        ag._tem_pacote = True
        except Exception:
            pass

        # Legenda de profissionais — compacta, numa só linha
        prof_vistos: dict = {}
        for ag in ags_periodo:
            prof_vistos.setdefault(ag.profissional, ag.cor_profissional or "#E3A5C7")
        if prof_vistos:
            badges = " ".join(
                f'<span style="background:{c};padding:3px 10px;border-radius:8px;'
                f'font-size:12px;margin-right:6px;display:inline-block;"><b>{p}</b></span>'
                for p, c in prof_vistos.items()
            )
            st.markdown(f'<div style="margin-bottom:6px;">{badges}</div>', unsafe_allow_html=True)

        # Calendário proporcional
        if vista == "Mês":
            # Renderizar grid mensal simplificado
            nomes_sem = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
            hoje = _hoje()
            mes_html = '<table style="width:100%;border-collapse:collapse;font-family:sans-serif;font-size:12px;">'
            mes_html += '<tr>'
            for ns in nomes_sem:
                mes_html += f'<th style="padding:6px;text-align:center;background:#f3f4f6;border:1px solid #e5e7eb;">{ns}</th>'
            mes_html += '</tr>'
            for i in range(0, len(dias), 7):
                mes_html += '<tr>'
                for dia in dias[i:i+7]:
                    bg = "#fef2f2" if dia == hoje else ("#f9fafb" if dia.month == data_ref.month else "#fff")
                    ags_dia = ags_por_dia.get(dia, [])
                    cell_content = f'<div style="font-weight:700;margin-bottom:2px;">{dia.day}</div>'
                    for ag in ags_dia[:3]:
                        cor = ag.cor_profissional or "#E3A5C7"
                        cell_content += (
                            f'<div style="font-size:10px;background:{cor};color:#fff;'
                            f'padding:1px 4px;border-radius:3px;margin-bottom:1px;'
                            f'overflow:hidden;white-space:nowrap;text-overflow:ellipsis;">'
                            f'{ag.hora_inicio} {ag.cliente_nome or ""}</div>'
                        )
                    if len(ags_dia) > 3:
                        cell_content += f'<div style="font-size:9px;color:#666;">+{len(ags_dia)-3} mais</div>'
                    mes_html += (
                        f'<td style="padding:4px;border:1px solid #e5e7eb;vertical-align:top;'
                        f'background:{bg};min-height:60px;width:14.28%;">{cell_content}</td>'
                    )
                mes_html += '</tr>'
            mes_html += '</table>'
            st.markdown(mes_html, unsafe_allow_html=True)
        else:
            cal_html = _render_calendario(dias, ags_por_dia, semana=(vista == "Semana"))
            st.markdown(cal_html, unsafe_allow_html=True)

        # ── Confirmação e ações ─────────────────────────────────────────────
        if ags_periodo:
            st.markdown("---")
            st.markdown("#### Agendamentos")
            for ag in sorted(ags_periodo, key=lambda x: (x.data, x.hora_inicio)):
                col_nome_ag, col_info, col_conf, col_menu = st.columns([2, 4, 1, 0.4])
                with col_nome_ag:
                    pacote_label = " 📦" if getattr(ag, "_tem_pacote", False) else ""
                    if st.button(f"{ag.cliente_nome or 'N/A'}{pacote_label}", key=f"nome_{ag.id}", use_container_width=True):
                        st.session_state["ag_popup_edit_id"] = ag.id
                        st.rerun()
                with col_info:
                    prefixo = f"**{ag.data.strftime('%d/%m')}** — " if vista != "Dia" else ""
                    icone_conf = " ✅" if ag.confirmado else ""
                    st.write(
                        f"{prefixo}**{ag.hora_inicio}–{ag.hora_fim}** | "
                        f"{ag.procedimento or ''} | {ag.profissional}"
                        f"{icone_conf}"
                    )
                with col_conf:
                    if not ag.confirmado:
                        if st.button("Confirmar", key=f"conf_{ag.id}", use_container_width=True):
                            ag.confirmado = True
                            db.commit()
                            # ── Desconta sessão de pacote se houver ──
                            try:
                                from models.sale import Sale, SaleItem, SessionUsage
                                if ag.cliente_id:
                                    # Prioridade: pacote vinculado diretamente ao agendamento
                                    item_vinculado = (
                                        db.get(SaleItem, ag.sale_item_id)
                                        if getattr(ag, "sale_item_id", None)
                                        else None
                                    )
                                    if item_vinculado and item_vinculado.sessoes_usadas < item_vinculado.sessoes_total:
                                        match_p = item_vinculado
                                    elif ag.procedimento:
                                        proc_norm = ag.procedimento.strip().lower()
                                        item_pacote = (
                                            db.query(SaleItem)
                                            .join(Sale)
                                            .filter(
                                                Sale.cliente_id == ag.cliente_id,
                                                SaleItem.tipo == "pacote",
                                                SaleItem.sessoes_usadas < SaleItem.sessoes_total,
                                            )
                                            .order_by(Sale.data_venda)
                                            .all()
                                        )
                                        match_p = next(
                                            (it for it in item_pacote if it.procedimento.strip().lower() == proc_norm),
                                            item_pacote[0] if item_pacote else None,
                                        )
                                    else:
                                        match_p = None
                                    if match_p:
                                        match_p.sessoes_usadas += 1
                                        db.add(SessionUsage(
                                            sale_item_id=match_p.id,
                                            agendamento_id=ag.id,
                                            data_uso=ag.data,
                                        ))
                                        db.commit()
                            except Exception:
                                pass
                            try:
                                _ulog = st.session_state.get("user", {})
                                db.add(AgendaLog(
                                    agendamento_id=ag.id,
                                    acao="confirmado",
                                    usuario_id=_ulog.get("id"),
                                    usuario_nome=_ulog.get("nome", ""),
                                    dados_depois=__import__("json").dumps({
                                        "cliente": ag.cliente_nome,
                                        "profissional": ag.profissional,
                                        "data": str(ag.data),
                                        "hora_inicio": ag.hora_inicio,
                                        "procedimento": ag.procedimento,
                                        "sala": ag.sala,
                                    }, ensure_ascii=False),
                                ))
                                db.commit()
                            except Exception:
                                pass
                            st.rerun()
                    else:
                        if st.button("✅ Confirmado", key=f"desc_{ag.id}", use_container_width=True):
                            ag.confirmado = False
                            db.commit()
                            st.rerun()
                # ⋮ sempre visível — independente do status de confirmação
                with col_menu:
                    with st.popover("⋮"):
                        if st.button("✏️ Editar", key=f"edit_{ag.id}", use_container_width=True):
                            cli_key = "— selecione —"
                            for k, (cid, _) in mapa_cli.items():
                                if cid == ag.cliente_id:
                                    cli_key = k
                                    break
                            st.session_state["ag_edit_id"] = ag.id
                            st.session_state["ag_pending_edit"] = {
                                "ag_cliente":  cli_key,
                                "ag_prof":     ag.profissional if ag.profissional in nomes_prof else "— selecione —",
                                "ag_proc":     ag.procedimento or "",
                                "ag_data":     ag.data,
                                "ag_hora_ini": ag.hora_inicio if ag.hora_inicio in slots else "08:00",
                                "ag_duracao":  ag.duracao_min if ag.duracao_min in duracoes else 60,
                                "ag_obs":      ag.observacoes or "",
                                "ag_sala":     ag.sala if ag.sala else "— selecione —",
                            }
                            st.rerun()
                        st.markdown("---")
                        if st.button("🗑️ Excluir", key=f"del_{ag.id}", use_container_width=True):
                            try:
                                _ulog = st.session_state.get("user", {})
                                db.add(AgendaLog(
                                    agendamento_id=ag.id,
                                    acao="excluido",
                                    usuario_id=_ulog.get("id"),
                                    usuario_nome=_ulog.get("nome", ""),
                                    dados_antes=__import__("json").dumps({
                                        "cliente": ag.cliente_nome, "profissional": ag.profissional,
                                        "data": str(ag.data), "hora_inicio": ag.hora_inicio,
                                        "procedimento": ag.procedimento, "sala": ag.sala,
                                    }, ensure_ascii=False),
                                ))
                                db.commit()
                            except Exception:
                                pass
                            db.delete(ag)
                            db.commit()
                            st.rerun()

        # ── Pop-up de edição rápida ──────────────────────────────────────────
        if "ag_popup_edit_id" in st.session_state:
            _popup_id = st.session_state["ag_popup_edit_id"]
            _ag_popup = db.get(ScheduledAppointment, _popup_id)
            if _ag_popup:
                @st.dialog("Editar Agendamento", width="large")
                def _dialog_editar_ag():
                    _db2 = SessionLocal()
                    try:
                        _ag2 = _db2.get(ScheduledAppointment, _popup_id)
                        if not _ag2:
                            st.error("Agendamento não encontrado.")
                            return
                        col_d1, col_d2 = st.columns(2)
                        with col_d1:
                            _ed_data = st.date_input("Data", value=_ag2.data, format="DD/MM/YYYY", key="dlg_ag_data")
                            _clientes_dlg = _db2.query(Client).order_by(Client.nome.asc()).all()
                            _opcoes_cli_dlg = ["— selecione —"] + [f"{c.nome} ({c.cpf or ''})" for c in _clientes_dlg]
                            _mapa_cli_dlg = {f"{c.nome} ({c.cpf or ''})": (c.id, c.nome) for c in _clientes_dlg}
                            _cli_atual = "— selecione —"
                            for k, (cid, _) in _mapa_cli_dlg.items():
                                if cid == _ag2.cliente_id:
                                    _cli_atual = k
                                    break
                            _ed_cli = st.selectbox("Cliente", _opcoes_cli_dlg, index=_opcoes_cli_dlg.index(_cli_atual) if _cli_atual in _opcoes_cli_dlg else 0, key="dlg_ag_cli")
                            _profs_dlg = _db2.query(Professional).order_by(Professional.nome.asc()).all()
                            _nomes_prof_dlg = [p.nome for p in _profs_dlg]
                            _idx_prof = _nomes_prof_dlg.index(_ag2.profissional) if _ag2.profissional in _nomes_prof_dlg else 0
                            _ed_prof = st.selectbox("Profissional", _nomes_prof_dlg, index=_idx_prof, key="dlg_ag_prof")
                        with col_d2:
                            _slots_dlg = gerar_slots_horario()
                            _idx_hora = _slots_dlg.index(_ag2.hora_inicio) if _ag2.hora_inicio in _slots_dlg else 0
                            _ed_hora = st.selectbox("Hora início", _slots_dlg, index=_idx_hora, key="dlg_ag_hora")
                            _duracoes_dlg = [15, 30, 45, 60, 75, 90, 105, 120]
                            _idx_dur = _duracoes_dlg.index(_ag2.duracao_min) if _ag2.duracao_min in _duracoes_dlg else 3
                            _ed_dur = st.selectbox("Duração (min)", _duracoes_dlg, index=_idx_dur, key="dlg_ag_dur")
                            _ed_proc = st.text_input("Procedimento", value=_ag2.procedimento or "", key="dlg_ag_proc")
                            _ed_obs = st.text_area("Observações", value=_ag2.observacoes or "", key="dlg_ag_obs")
                            OPCOES_SALA_DLG = ["— nenhuma —", "Sala 1", "Sala 2", "Sala 3", "Sala 4", "Sala 5", "Soroterapia"]
                            _sala_idx = OPCOES_SALA_DLG.index(_ag2.sala) if _ag2.sala in OPCOES_SALA_DLG else 0
                            _ed_sala = st.selectbox("Sala", OPCOES_SALA_DLG, index=_sala_idx, key="dlg_ag_sala")

                        col_sv, col_cn = st.columns(2)
                        with col_sv:
                            if st.button("Salvar", use_container_width=True, key="dlg_ag_save", type="primary"):
                                _ag2.data = _ed_data
                                _ag2.hora_inicio = _ed_hora
                                _ag2.hora_fim = calcular_hora_fim(_ed_hora, _ed_dur)
                                _ag2.duracao_min = _ed_dur
                                if _ed_cli != "— selecione —" and _ed_cli in _mapa_cli_dlg:
                                    _ag2.cliente_id, _ag2.cliente_nome = _mapa_cli_dlg[_ed_cli]
                                _ag2.profissional = _ed_prof
                                _ag2.procedimento = _ed_proc.strip()
                                _ag2.observacoes = _ed_obs
                                _ag2.sala = _ed_sala if _ed_sala != "— nenhuma —" else None
                                _cor_map = {p.nome: (p.cor or "#E3A5C7") for p in _profs_dlg}
                                _ag2.cor_profissional = _cor_map.get(_ed_prof, "#E3A5C7")
                                _db2.commit()
                                st.session_state.pop("ag_popup_edit_id", None)
                                st.rerun()
                        with col_cn:
                            if st.button("Cancelar", use_container_width=True, key="dlg_ag_cancel"):
                                st.session_state.pop("ag_popup_edit_id", None)
                                st.rerun()
                    finally:
                        _db2.close()
                _dialog_editar_ag()

        # ── Gerenciar Profissionais ──────────────────────────────────────────
        st.markdown("---")
        st.markdown("### Profissionais")
        profs_db = db.query(Professional).order_by(Professional.nome.asc()).all()
        if profs_db:
            for p in profs_db:
                col_cor, col_nome, col_btn = st.columns([0.4, 4, 0.4])
                with col_cor:
                    st.markdown(
                        f'<div style="width:22px;height:22px;background:{p.cor};'
                        f'border-radius:50%;margin-top:10px;"></div>',
                        unsafe_allow_html=True,
                    )
                with col_nome:
                    st.write(p.nome)
                with col_btn:
                    with st.popover("⋮", use_container_width=True):
                        if st.button("✏️ Editar", key=f"prof_edit_{p.id}"):
                            st.session_state["prof_editando"] = p.id
                            st.rerun()
                        if st.button("🗑️ Remover", key=f"rem_prof_{p.id}", use_container_width=True):
                            db.delete(p)
                            db.commit()
                            st.rerun()
            # Formulário de edição de profissional
            if st.session_state.get("prof_editando"):
                _pid = st.session_state["prof_editando"]
                _prof_ed = db.get(Professional, _pid)
                if _prof_ed:
                    st.markdown("---")
                    st.markdown("##### Editar Profissional")
                    with st.form("form_editar_prof", clear_on_submit=False):
                        _ed_prof_nome = st.text_input("Nome", value=_prof_ed.nome, key="ed_prof_nome")
                        _ed_prof_cor = st.selectbox(
                            "Cor", list(CORES_PROFISSIONAIS.keys()),
                            index=list(CORES_PROFISSIONAIS.values()).index(_prof_ed.cor)
                            if _prof_ed.cor in CORES_PROFISSIONAIS.values() else 0,
                            key="ed_prof_cor",
                        )
                        col_psv, col_pcn = st.columns(2)
                        with col_psv:
                            _salvar_prof = st.form_submit_button("💾 Salvar", use_container_width=True)
                        with col_pcn:
                            _cancelar_prof = st.form_submit_button("Cancelar", use_container_width=True)
                    if _salvar_prof:
                        if not _ed_prof_nome.strip():
                            st.error("Informe o nome.")
                        else:
                            _prof_ed.nome = _ed_prof_nome.strip()
                            _prof_ed.cor = CORES_PROFISSIONAIS[_ed_prof_cor]
                            db.commit()
                            st.success("Profissional atualizado!")
                            st.session_state.pop("prof_editando", None)
                            st.rerun()
                    if _cancelar_prof:
                        st.session_state.pop("prof_editando", None)
                        st.rerun()
        else:
            st.info("Nenhum profissional cadastrado.")

        st.markdown("#### Cadastrar profissional")
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            novo_nome = st.text_input("Nome", key="novo_prof_nome", label_visibility="collapsed",
                                      placeholder="Nome do profissional")
        with col2:
            cor_escolhida = st.selectbox("Cor", list(CORES_PROFISSIONAIS.keys()), key="novo_prof_cor",
                                         label_visibility="collapsed")
        with col3:
            if st.button("Adicionar", use_container_width=True, key="btn_add_prof"):
                if novo_nome.strip():
                    existe = db.query(Professional).filter(Professional.nome == novo_nome.strip()).first()
                    if existe:
                        st.warning("Profissional já cadastrado.")
                    else:
                        db.add(Professional(nome=novo_nome.strip(), cor=CORES_PROFISSIONAIS[cor_escolhida]))
                        db.commit()
                        st.success(f"{novo_nome} adicionado!")
                        st.rerun()
                else:
                    st.error("Informe o nome.")

        # ── Histórico de Agendamentos ───────────────────────────────────────
        _data_hoje = _hoje()
        _ini_mes = _data_hoje.replace(day=1)
        st.markdown("---")
        with st.expander("📋 Histórico de agendamentos", expanded=False):
            col_hi, col_hf, col_att = st.columns([1, 1, 1])
            with col_hi:
                _log_ini = st.date_input("De", value=_ini_mes, key="log_ini", format="DD/MM/YYYY")
            with col_hf:
                _log_fim = st.date_input("Até", value=_data_hoje, key="log_fim", format="DD/MM/YYYY")
            with col_att:
                st.markdown("&nbsp;", unsafe_allow_html=True)
                if st.button("🔄 Atualizar", use_container_width=True, key="log_refresh"):
                    st.rerun()

            try:
                _logs = (
                    db.query(AgendaLog)
                    .filter(AgendaLog.criado_em >= _log_ini, AgendaLog.criado_em <= _log_fim)
                    .order_by(AgendaLog.criado_em.desc())
                    .all()
                )
                if not _logs:
                    st.info("Nenhum registro no período.")
                else:
                    import json as _json
                    _CORES_ACAO = {
                        "criado": "🟢", "editado": "🟡",
                        "confirmado": "🔵", "excluido": "🔴",
                    }
                    _rows = []
                    for _l in _logs:
                        _depois = _json.loads(_l.dados_depois or "{}") if _l.dados_depois else {}
                        _antes = _json.loads(_l.dados_antes or "{}") if _l.dados_antes else {}
                        _base = _depois if _depois else _antes
                        _data_ag = _base.get("data", "—")
                        try:
                            from datetime import datetime as _dt
                            _data_ag = _dt.strptime(_data_ag, "%Y-%m-%d").strftime("%d/%m/%Y") if _data_ag and _data_ag != "—" else "—"
                        except Exception:
                            pass
                        _rows.append({
                            "Data do Agendamento": _data_ag,
                            "Data/Hora da Ação": _l.criado_em.strftime("%d/%m/%Y %H:%M") if _l.criado_em else "—",
                            "Ação": f"{_CORES_ACAO.get(_l.acao, '')} {_l.acao}",
                            "Paciente": _base.get("cliente", "—"),
                            "Profissional": _base.get("profissional", "—"),
                            "Procedimento": _base.get("procedimento", "—"),
                            "Sala": _base.get("sala", "—"),
                            "Usuário": _l.usuario_nome or "—",
                        })
                    import pandas as _pd
                    st.dataframe(_pd.DataFrame(_rows), use_container_width=True, hide_index=True)
            except Exception as _e:
                st.warning(f"Não foi possível carregar o histórico: {_e}")

    finally:
        db.close()


# ====== TELA: CADASTRO DE CLIENTE ======
def _modal_cliente(titulo: str, cliente_id: int = 0):
    """Modal reutilizável para criar ou editar cliente.
    Abre via st.dialog — sempre lê dados frescos do banco.
    """
    @st.dialog(titulo, width="large")
    def _abrir():
        db = SessionLocal()
        try:
            c = db.get(Client, cliente_id) if cliente_id else None

            def v(campo, default=""):
                if c is None:
                    return default
                val = getattr(c, campo, None)
                return val if val is not None else default

            def vf(campo):
                val = getattr(c, campo, None) if c else None
                return float(val) if val else 0.0

            def vb(campo):
                return bool(getattr(c, campo, False)) if c else False

            prefix = f"ed{cliente_id}_" if cliente_id else "nc_"

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                nome   = st.text_input("Nome completo*",      value=v("nome"),      key=f"{prefix}nome")
                cpf    = st.text_input("CPF",                 value=v("cpf"),       key=f"{prefix}cpf")
                nasc_default = c.data_nascimento if (c and c.data_nascimento) else _hoje()
                nasc   = st.date_input("Data de nascimento",  value=nasc_default,   key=f"{prefix}nasc",   format="DD/MM/YYYY")
                tel    = st.text_input("Telefone",            value=v("telefone"),  key=f"{prefix}tel")
                email  = st.text_input("E-mail",              value=v("email"),     key=f"{prefix}email")
                prof   = st.text_input("Profissão",           value=v("profissao"), key=f"{prefix}prof")

            with col_b:
                end    = st.text_input("Endereço",            value=v("endereco"),  key=f"{prefix}end")
                bairro = st.text_input("Bairro",              value=v("bairro"),    key=f"{prefix}bairro")
                cidade = st.text_input("Cidade",              value=v("cidade"),    key=f"{prefix}cidade")
                peso   = st.number_input("Peso (kg)",         value=vf("peso"),     min_value=0.0, step=0.1, key=f"{prefix}peso")
                altura = st.number_input("Altura (m)",        value=vf("altura"),   min_value=0.0, step=0.01, key=f"{prefix}altura")
                imc_v  = calcular_imc(peso, altura)
                st.text_input("IMC (calculado)",              value=str(imc_v) if imc_v else "", disabled=True)
                exames = st.text_area("Exames recentes",      value=v("exames_recentes"), key=f"{prefix}exames")

            with col_c:
                func_int = st.text_input("Funcionamento intestinal", value=v("funcionamento_intestinal"), key=f"{prefix}func")
                uso_vit  = st.text_area("Uso de vitaminas",          value=v("uso_vitaminas"),            key=f"{prefix}vit")
                marcacao = st.text_area("Marcação corporal",          value=v("marcacao_corporal"),        key=f"{prefix}marc")
                neo      = st.checkbox("Neoplasia",   value=vb("neoplasia"),  key=f"{prefix}neo")
                epi      = st.checkbox("Epilepsia",   value=vb("epilepsia"),  key=f"{prefix}epi")
                outras   = st.text_area("Outras condições médicas",  value=v("outras_condicoes"),         key=f"{prefix}outras")
                queixa   = st.text_area("Queixa principal",          value=v("queixa_principal"),         key=f"{prefix}queixa")
                termo    = st.checkbox("Aceito o termo de veracidade", value=vb("termo_aceite"),          key=f"{prefix}termo")

            st.markdown("---")
            label_btn = "💾 Salvar alterações" if cliente_id else "💾 Salvar novo cliente"
            if st.button(label_btn, use_container_width=True, type="primary"):
                if not nome.strip():
                    st.error("Nome é obrigatório.")
                    return
                imc_sal = calcular_imc(peso, altura)
                dados = dict(
                    nome=nome.strip(), cpf=cpf.strip() or None,
                    data_nascimento=nasc, telefone=tel or None,
                    email=email or None, profissao=prof or None,
                    endereco=end or None, bairro=bairro or None,
                    cidade=cidade or None, peso=peso or None,
                    altura=altura or None, imc=imc_sal or None,
                    exames_recentes=exames or None,
                    funcionamento_intestinal=func_int or None,
                    uso_vitaminas=uso_vit or None,
                    marcacao_corporal=marcacao or None,
                    neoplasia=neo, epilepsia=epi,
                    outras_condicoes=outras or None,
                    queixa_principal=queixa or None,
                    termo_aceite=termo,
                )
                if cliente_id and c:
                    for k, val in dados.items():
                        setattr(c, k, val)
                    db.commit()
                    st.success("Cliente atualizada com sucesso!")
                else:
                    db.add(Client(**dados))
                    db.commit()
                    st.success(f"Cliente '{nome}' cadastrada!")
                st.rerun()
        finally:
            db.close()

    _abrir()


def tela_clientes():
    header_titulo("Clientes", "Busca, cadastro, ficha completa e histórico")

    # ── Barra de ação ──
    _cli_id_top = st.session_state.get("cliente_id_edicao", 0)
    col_sync, col_novo, col_edit, _ = st.columns([1, 1, 1, 2])
    with col_sync:
        if st.button("🔄 Sincronizar", use_container_width=True):
            try:
                with st.spinner("Sincronizando..."):
                    r = sincronizar_clientes()
                st.success(
                    f"✅ {r['importados']} novos · 🔄 {r['atualizados']} atualizados · ⏭️ {r['pulados']} pulados"
                )
                if r["pulados_nomes"]:
                    with st.expander(f"Ver {len(r['pulados_nomes'])} pulado(s)"):
                        for n in r["pulados_nomes"]:
                            st.caption(f"• {n}")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao sincronizar: {e}")
    with col_novo:
        if st.button("➕ Novo Cliente", use_container_width=True):
            _modal_cliente("Novo Cliente", 0)
    with col_edit:
        if _cli_id_top:
            if st.button("✏️ Editar", use_container_width=True, key="btn_editar_top"):
                _modal_cliente("Editar Cliente", _cli_id_top)

    db = SessionLocal()
    try:
        # ── Busca ──
        st.markdown("#### Buscar cliente")
        render_sugestoes_cliente(db, "", "cadastro")

        cliente_id = st.session_state.get("cliente_id_edicao", 0)

        if not cliente_id:
            st.info('Use a busca acima para selecionar uma cliente, ou clique em "➕ Novo Cliente".')
        else:
            c = db.get(Client, cliente_id)
            if not c:
                st.warning("Cliente não encontrado no banco.")
            else:
                # ── Cabeçalho: nome em destaque ──
                st.markdown(
                    f'<p style="font-size:1.9rem;font-weight:700;color:#b87575;'
                    f'font-family:\'Cormorant Garamond\',serif;margin:0.2rem 0 0.8rem 0;">'
                    f'{c.nome}</p>',
                    unsafe_allow_html=True,
                )

                # ── Mini-resumo de pacotes ativos ──────────────────────────
                try:
                    from models.sale import Sale, SaleItem
                    _pkt = (
                        db.query(SaleItem)
                        .join(Sale)
                        .filter(
                            Sale.cliente_id == cliente_id,
                            SaleItem.tipo == "pacote",
                            SaleItem.sessoes_usadas < SaleItem.sessoes_total,
                        ).all()
                    )
                    if _pkt:
                        for _p in _pkt:
                            rest = _p.sessoes_total - _p.sessoes_usadas
                            st.info(f"📦 Pacote ativo: **{_p.procedimento}** — {rest} sessão(ões) restante(s)")
                except Exception:
                    pass

                def row(label, val):
                    return f"**{label}:** {val or '—'}"

                # ── DADOS PESSOAIS ──────────────────────────────────────────
                st.markdown("##### Dados Pessoais")
                col_a, col_b = st.columns(2)

                with col_a:
                    st.markdown(row("CPF", c.cpf))
                    nasc = c.data_nascimento.strftime("%d/%m/%Y") if c.data_nascimento else "—"
                    st.markdown(row("Nascimento", nasc))
                    st.markdown(row("Telefone", c.telefone))
                    st.markdown(row("E-mail", c.email))
                    st.markdown(row("Profissão", c.profissao))
                    st.markdown(row("Queixa principal", c.queixa_principal))
                    termo_txt = "Aceito" if c.termo_aceite else "Não"
                    st.markdown(f"**Termo:** {termo_txt}")

                with col_b:
                    st.markdown(row("Endereço", c.endereco))
                    st.markdown(row("Bairro", c.bairro))
                    st.markdown(row("Cidade", c.cidade))
                    st.markdown(row("Peso", f"{c.peso} kg" if c.peso else None))
                    st.markdown(row("Altura", f"{c.altura} m" if c.altura else None))
                    st.markdown(row("IMC", c.imc))
                    st.markdown(row("Exames recentes", c.exames_recentes))
                    st.markdown(row("Func. intestinal", c.funcionamento_intestinal))
                    st.markdown(row("Uso de vitaminas", c.uso_vitaminas))

                # ── CONDIÇÕES MÉDICAS ───────────────────────────────────────
                st.markdown("---")
                st.markdown("##### Condições Médicas")

                # Condições booleanas fixas
                _cond_fixas = [
                    ("Neoplasia", c.neoplasia),
                    ("Epilepsia", c.epilepsia),
                ]
                _cols_med = st.columns(3)
                _idx_med = 0
                for _label, _bool_val in _cond_fixas:
                    _txt = "Sim" if _bool_val else "Não"
                    with _cols_med[_idx_med % 3]:
                        st.markdown(f"**{_label}:** {_txt}")
                    _idx_med += 1

                # Condições vindas de outras_condicoes (texto multilinhas)
                _SEM_ICONE = {"MEDICAMENTOS EM USO", "FUMA", "CONSUMO DE ÁLCOOL"}
                if c.outras_condicoes:
                    _linhas_cond = [l.strip() for l in c.outras_condicoes.split("\n") if l.strip()]
                    for _linha in _linhas_cond:
                        if ":" in _linha:
                            _rot, _val = _linha.split(":", 1)
                            _rot = _rot.strip()
                            _val = _val.strip()
                        else:
                            _rot, _val = _linha.strip(), ""
                        _rot_upper = _rot.upper()
                        _is_sim = _val.lower() in ("sim", "yes", "1", "true", "x", "ok") or (
                            "sim" in _val.lower() and _rot_upper not in _SEM_ICONE
                        )
                        if _rot_upper in _SEM_ICONE:
                            _exibir = _val if _val else "Não informado"
                        else:
                            _exibir = "Sim" if _is_sim else (_val if _val else "Não informado")
                        with _cols_med[_idx_med % 3]:
                            st.markdown(f"**{_rot}:** {_exibir}")
                        _idx_med += 1

                # ── Histórico em abas ──
                st.markdown("---")
                abas = st.tabs(["📋 Atendimentos", "📐 Biometria", "📝 Pré-avaliações", "💳 Compras e Pacotes", "💉 Tabela de Doses"])

                with abas[0]:
                    atend = pd.read_sql(
                        db.query(Appointment).filter(Appointment.cliente_id == cliente_id)
                        .order_by(Appointment.data.desc()).statement, db.bind,
                    )
                    if not atend.empty:
                        if "data" in atend.columns:
                            atend["data"] = pd.to_datetime(atend["data"], errors="coerce").dt.strftime("%d/%m/%Y")
                        st.dataframe(atend, use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhum atendimento encontrado.")

                with abas[1]:
                    bio = pd.read_sql(
                        db.query(Biometrics).filter(Biometrics.cliente_id == cliente_id)
                        .order_by(Biometrics.data_medicao.desc()).statement, db.bind,
                    )
                    if not bio.empty:
                        if "data_medicao" in bio.columns:
                            bio["data_medicao"] = pd.to_datetime(bio["data_medicao"], errors="coerce").dt.strftime("%d/%m/%Y")
                        st.dataframe(bio, use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhuma biometria cadastrada.")

                with abas[2]:
                    try:
                        aval = pd.read_sql(
                            db.query(Assessment).filter(Assessment.cliente_id == cliente_id)
                            .order_by(Assessment.criado_em.desc()).statement, db.bind,
                        )
                        if not aval.empty:
                            if "criado_em" in aval.columns:
                                aval["criado_em"] = pd.to_datetime(aval["criado_em"], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")
                            st.dataframe(aval, use_container_width=True, hide_index=True)
                        else:
                            st.info("Nenhuma pré-avaliação encontrada.")
                    except Exception:
                        st.info("Nenhuma pré-avaliação encontrada.")

                with abas[3]:
                    vendas = (
                        db.query(Sale)
                        .filter(Sale.cliente_id == cliente_id)
                        .order_by(Sale.data_venda.desc())
                        .all()
                    )
                    if not vendas:
                        st.info("Nenhuma compra registrada para esta cliente.")
                    else:
                        rows = []
                        for v in vendas:
                            for it in v.itens:
                                saldo = it.sessoes_total - it.sessoes_usadas
                                rows.append({
                                    "Data": v.data_venda.strftime("%d/%m/%Y"),
                                    "Procedimento": it.procedimento,
                                    "Tipo": it.tipo.capitalize(),
                                    "Total Sessões": it.sessoes_total,
                                    "Usadas": it.sessoes_usadas,
                                    "Saldo": saldo,
                                    "Valor (R$)": f"{it.valor:.2f}",
                                    "Pagamento": v.forma_pagamento,
                                })
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                with abas[4]:
                    doses = db.query(DoseTable).filter(
                        DoseTable.cliente_id == cliente_id
                    ).order_by(DoseTable.criado_em.desc()).all()
                    
                    if doses:
                        dados_doses = [{
                            "Data": d.data_registro.strftime("%d/%m/%Y") if d.data_registro else "—",
                            "Medicação": d.medicacao,
                            "Semana": d.semana or "—",
                            "Dose": d.dose or "—",
                            "Via": d.via or "—",
                            "Peso": f"{d.peso} kg" if d.peso else "—",
                        } for d in doses]
                        st.dataframe(pd.DataFrame(dados_doses), use_container_width=True, hide_index=True)
                        
                        # Botão PDF
                        if st.button("📄 Gerar PDF da tabela de doses", use_container_width=True, key="dose_pdf_cliente"):
                            try:
                                from fpdf import FPDF
                                import os
                                
                                # Cores do sistema
                                COR_ROSA = (213, 156, 156)
                                COR_ROSA_CLARO = (255, 240, 238)
                                COR_BRANCO = (255, 255, 255)
                                COR_TEXTO = (74, 48, 48)
                                
                                class PDFTabelaDoses(FPDF):
                                    def header(self):
                                        self.set_fill_color(*COR_ROSA_CLARO)
                                        self.rect(0, 0, 210, 297, 'F')
                                        self.set_fill_color(*COR_ROSA)
                                        self.rect(0, 0, 210, 60, 'F')
                                        logo_carregada = False
                                        try:
                                            possiveis_caminhos = [
                                                os.path.join(os.path.dirname(__file__), "ui", "logogf.png"),
                                                os.path.join(os.path.dirname(__file__), "assets", "logogf.png"),
                                                "C:\\Users\\joaoz\\Desktop\\sistema GF\\ui\\logogf.png",
                                            ]
                                            for caminho in possiveis_caminhos:
                                                if os.path.exists(caminho):
                                                    self.image(caminho, x=85, y=10, w=40)
                                                    logo_carregada = True
                                                    break
                                        except:
                                            pass
                                        if not logo_carregada:
                                            self.set_y(16)
                                            self.set_font("Helvetica", "B", 28)
                                            self.set_text_color(*COR_BRANCO)
                                            self.cell(0, 14, "GABRIELA FRANCO", ln=True, align="C")
                                            self.set_font("Helvetica", "", 20)
                                            self.cell(0, 10, "SAUDE INTEGRATIVA", ln=True, align="C")
                                        self.ln(45)
                                    
                                    def footer(self):
                                        self.set_y(-25)
                                        self.set_fill_color(*COR_ROSA)
                                        self.rect(0, self.get_y(), 210, 25, 'F')
                                        self.set_y(-20)
                                        self.set_font("Helvetica", "", 9)
                                        self.set_text_color(*COR_BRANCO)
                                        self.cell(0, 5, "Praça São Judas Tadeu, 160 - Jardim Casqueiro - Cubatão", ln=True, align="C")
                                        self.cell(0, 5, "@gabifrancosaude - (13) 3304-0528", ln=True, align="C")
                                
                                pdf = PDFTabelaDoses()
                                pdf.add_page()
                                pdf.set_auto_page_break(auto=True, margin=30)
                                
                                cli = db.get(Client, cliente_id)
                                
                                # Título
                                pdf.set_font("Helvetica", "B", 18)
                                pdf.set_text_color(*COR_ROSA)
                                pdf.cell(0, 10, "TABELA DE DOSES", ln=True, align="C")
                                pdf.ln(8)
                                
                                # Dados do paciente
                                pdf.set_font("Helvetica", "B", 12)
                                pdf.set_text_color(*COR_ROSA)
                                nome_pac = cli.nome if cli else 'N/A'
                                pdf.cell(pdf.get_string_width("Paciente: ") + 2, 8, "Paciente: ", 0, 0)
                                pdf.set_text_color(0, 0, 0)
                                pdf.cell(0, 8, nome_pac, ln=True)
                                pdf.set_font("Helvetica", "", 10)
                                pdf.set_text_color(*COR_ROSA)
                                pdf.cell(pdf.get_string_width("Data: ") + 2, 6, "Data: ", 0, 0)
                                pdf.set_text_color(0, 0, 0)
                                from datetime import datetime as _dt
                                pdf.cell(0, 6, _dt.now().strftime("%d/%m/%Y"), ln=True)
                                pdf.ln(6)
                                
                                # Tabela
                                pdf.set_draw_color(*COR_ROSA)
                                pdf.set_font("Helvetica", "B", 10)
                                pdf.set_fill_color(*COR_ROSA)
                                pdf.set_text_color(*COR_BRANCO)
                                pdf.cell(35, 8, "Data", 1, 0, 'C', True)
                                pdf.cell(40, 8, "Medicação", 1, 0, 'C', True)
                                pdf.cell(25, 8, "Semana", 1, 0, 'C', True)
                                pdf.cell(30, 8, "Dose", 1, 0, 'C', True)
                                pdf.cell(25, 8, "Via", 1, 0, 'C', True)
                                pdf.cell(25, 8, "Peso", 1, 0, 'C', True)
                                pdf.ln()
                                
                                pdf.set_font("Helvetica", "", 9)
                                pdf.set_text_color(*COR_TEXTO)
                                for d in doses:
                                    pdf.cell(35, 8, d.data_registro.strftime("%d/%m/%Y") if d.data_registro else "—", 1)
                                    pdf.cell(40, 8, d.medicacao[:18], 1)
                                    pdf.cell(25, 8, (d.semana or "—")[:10], 1)
                                    pdf.cell(30, 8, (d.dose or "—")[:12], 1)
                                    pdf.cell(25, 8, (d.via or "—")[:10], 1)
                                    pdf.cell(25, 8, f"{d.peso} kg" if d.peso else "—", 1)
                                    pdf.ln()
                                
                                pdf_bytes = bytes(pdf.output())
                                st.download_button(
                                    "⬇️ Baixar PDF",
                                    data=pdf_bytes,
                                    file_name=f"tabela_doses_{cli.nome.replace(' ', '_') if cli else 'cliente'}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                            except Exception as e:
                                st.error(f"Erro ao gerar PDF: {e}")
                    else:
                        st.info("Nenhuma dose registrada para esta cliente.")

        st.markdown("---")
        st.markdown("#### Clientes cadastradas")
        df_clientes = pd.read_sql(
            db.query(Client).order_by(Client.id.desc()).statement, db.bind
        )
        if not df_clientes.empty:
            colunas = [c for c in ["id", "nome", "cpf", "telefone", "email", "cidade"] if c in df_clientes.columns]
            st.dataframe(df_clientes[colunas], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum cliente encontrado.")
    finally:
        db.close()




# ====== TELA: PRÉ-AVALIAÇÃO ======
def _gerar_pdf_pre_avaliacao(cliente_nome: str, cpf: str, avaliacao) -> bytes:
    """Gera PDF da pré-avaliação usando fpdf2 e retorna bytes."""
    try:
        from fpdf import FPDF
        import os
    except ImportError:
        return b""
    
    # Cores do sistema
    COR_ROSA = (213, 156, 156)
    COR_ROSA_CLARO = (255, 240, 238)
    COR_BRANCO = (255, 255, 255)
    COR_TEXTO = (74, 48, 48)
    
    class PDFPreAvaliacao(FPDF):
        def header(self):
            self.set_fill_color(*COR_ROSA_CLARO)
            self.rect(0, 0, 210, 297, 'F')
            self.set_fill_color(245, 220, 220)
            self.rect(0, 0, 210, 60, 'F')
            try:
                possiveis_caminhos = [
                    os.path.join(os.path.dirname(__file__), "ui", "logogf.png"),
                    os.path.join(os.path.dirname(__file__), "assets", "logogf.png"),
                ]
                for caminho in possiveis_caminhos:
                    if os.path.exists(caminho):
                        self.image(caminho, x=75, y=20, w=60)
                        break
            except:
                pass
            self.ln(55)
        
        def footer(self):
            self.set_y(-25)
            self.set_fill_color(*COR_ROSA)
            self.rect(0, self.get_y(), 210, 25, 'F')
            self.set_y(-20)
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*COR_BRANCO)
            self.cell(0, 5, "Praça São Judas Tadeu, 160 - Jardim Casqueiro - Cubatão", ln=True, align="C")
            self.cell(0, 5, "@gabifrancosaude - (13) 3304-0528", ln=True, align="C")

    pdf = PDFPreAvaliacao()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=30)

    # Título
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*COR_ROSA)
    pdf.cell(0, 10, "PRÉ-AVALIAÇÃO / CONSULTA", ln=True, align="C")
    pdf.ln(5)
    
    # Linha decorativa
    pdf.set_draw_color(*COR_ROSA)
    pdf.set_line_width(0.5)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(10)

    # Dados do cliente
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*COR_TEXTO)
    pdf.cell(0, 8, f"{avaliacao.criado_em.strftime('%d/%m/%Y') if avaliacao.criado_em else ''}", ln=True)
    pdf.cell(0, 8, f"{cliente_nome}", ln=True)
    pdf.cell(0, 8, f"CPF: {cpf or '—'}", ln=True)
    pdf.ln(8)

    def campo(label: str, valor: str):
        if not valor:
            return
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*COR_ROSA)
        pdf.cell(0, 6, label, ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*COR_TEXTO)
        pdf.multi_cell(0, 6, valor)
        pdf.ln(2)

    campo("Queixa detalhada:", avaliacao.queixa_detalhada or "")
    campo("Objetivo do tratamento:", avaliacao.objetivo_tratamento or "")
    campo("Avaliação inicial:", avaliacao.avaliacao_inicial or "")
    campo("Receituário (Indicação de tratamento):", avaliacao.receituario or "")
    campo("Observações profissionais:", avaliacao.observacoes_profissionais or "")

    return bytes(pdf.output())


def tela_pre_avaliacao():
    header_titulo("Pré-avaliação", "Vinculada ao cliente e salva no histórico")
    db = SessionLocal()
    try:
        clientes = db.query(Client).order_by(Client.nome.asc()).all()
        mapa = {f"{c.nome} ({c.cpf or ''})": c.id for c in clientes}
        opcoes_cli = ["— selecione —"] + list(mapa.keys())
        cliente_sel = st.selectbox("Cliente", opcoes_cli)

        if cliente_sel and cliente_sel != "— selecione —":
            cid = mapa[cliente_sel]
            cli = db.get(Client, cid)

            queixa = st.text_area("Queixa detalhada", height=100)
            objetivo = st.text_area("Objetivo do tratamento", height=100)
            avaliacao_ini = st.text_area("Avaliação inicial", height=100)
            receituario = st.text_area(
                "Receituário (Indicação de tratamento)",
                height=200,
                placeholder="Descreva os tratamentos, protocolos e indicações para esta paciente...",
            )
            obs = st.text_area("Observações profissionais", height=100)

            if st.button("Salvar pré-avaliação", use_container_width=True):
                a = Assessment(
                    cliente_id=cid,
                    queixa_detalhada=queixa,
                    objetivo_tratamento=objetivo,
                    avaliacao_inicial=avaliacao_ini,
                    receituario=receituario,
                    observacoes_profissionais=obs,
                )
                db.add(a)
                db.commit()
                st.success("Pré-avaliação registrada.")
                st.rerun()

            # ── Histórico + botão PDF ──────────────────────────────────────
            st.markdown("---")
            st.markdown("#### Histórico de pré-avaliações")
            avaliacoes = (
                db.query(Assessment)
                .filter(Assessment.cliente_id == cid)
                .order_by(Assessment.criado_em.desc())
                .all()
            )
            if not avaliacoes:
                st.info("Nenhuma pré-avaliação registrada para esta cliente.")
            else:
                for av in avaliacoes:
                    data_str = av.criado_em.strftime("%d/%m/%Y %H:%M") if av.criado_em else "—"
                    with st.expander(f"📋 {data_str}"):
                        if av.queixa_detalhada:
                            st.markdown(f"**Queixa:** {av.queixa_detalhada}")
                        if av.objetivo_tratamento:
                            st.markdown(f"**Objetivo:** {av.objetivo_tratamento}")
                        if av.avaliacao_inicial:
                            st.markdown(f"**Avaliação inicial:** {av.avaliacao_inicial}")
                        if av.receituario:
                            st.markdown(f"**Receituário:** {av.receituario}")
                        if av.observacoes_profissionais:
                            st.markdown(f"**Observações:** {av.observacoes_profissionais}")

                        pdf_bytes = _gerar_pdf_pre_avaliacao(
                            cli.nome if cli else "", cli.cpf if cli else "", av
                        )
                        if pdf_bytes:
                            st.download_button(
                                "📄 Baixar PDF",
                                data=pdf_bytes,
                                file_name=f"pre_avaliacao_{cid}_{data_str.replace('/', '-').replace(' ', '_').replace(':', '')}.pdf",
                                mime="application/pdf",
                                key=f"pdf_av_{av.id}",
                            )
    finally:
        db.close()


# ====== MODAIS ATENDIMENTOS ======
def _modal_receituario_popup():
    @st.dialog("Gerar Receituário", width="large")
    def _abrir():
        db = SessionLocal()
        try:
            # Busca cliente
            clientes = db.query(Client).order_by(Client.nome.asc()).all()
            mapa_cli = {f"{c.nome} ({c.cpf or ''})": c for c in clientes}
            opcoes_cli = ["— selecione —"] + list(mapa_cli.keys())
            
            cliente_sel = st.selectbox("Selecione o cliente", opcoes_cli, key="rec_popup_cliente")
            
            if cliente_sel != "— selecione —":
                cliente = mapa_cli[cliente_sel]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Paciente:** {cliente.nome}")
                with col2:
                    data_rec = st.date_input("Data", value=_hoje(), key="rec_popup_data")
                
                receituario_txt = st.text_area(
                    "Receituário (Indicação de Tratamento)",
                    height=200,
                    placeholder="Descreva os tratamentos, protocolos e indicações...",
                    key="rec_popup_texto"
                )
                
                if st.button("📄 Gerar PDF do Receituário", use_container_width=True, key="rec_popup_gerar"):
                    if not receituario_txt or receituario_txt.strip() == "":
                        st.warning("Preencha o receituário antes de gerar o PDF.")
                    else:
                        try:
                            from fpdf import FPDF
                            
                            # Cores do sistema
                            COR_ROSA = (213, 156, 156)  # #D59C9C
                            COR_ROSA_CLARO = (255, 240, 238)  # #fff0ee - cor das abas
                            COR_BRANCO = (255, 255, 255)
                            COR_TEXTO = (74, 48, 48)  # #4a3030
                            
                            class PDFReceituario(FPDF):
                                def header(self):
                                    self.set_fill_color(*COR_ROSA_CLARO)
                                    self.rect(0, 0, 210, 297, 'F')
                                    self.set_fill_color(245, 220, 220)
                                    self.rect(0, 0, 210, 60, 'F')
                                    try:
                                        possiveis_caminhos = [
                                            os.path.join(os.path.dirname(__file__), "ui", "logogf.png"),
                                            os.path.join(os.path.dirname(__file__), "assets", "logogf.png"),
                                        ]
                                        for caminho in possiveis_caminhos:
                                            if os.path.exists(caminho):
                                                self.image(caminho, x=75, y=20, w=60)
                                                break
                                    except:
                                        pass
                                    self.ln(55)
                                
                                def footer(self):
                                    # Fundo rosa mais escuro no rodapé
                                    self.set_y(-25)
                                    self.set_fill_color(*COR_ROSA)
                                    self.rect(0, self.get_y(), 210, 25, 'F')
                                    
                                    # Texto do rodapé em branco
                                    self.set_y(-20)
                                    self.set_font("Helvetica", "", 9)
                                    self.set_text_color(*COR_BRANCO)
                                    self.cell(0, 5, "Praça São Judas Tadeu, 160 - Jardim Casqueiro - Cubatão", ln=True, align="C")
                                    self.cell(0, 5, "@gabifrancosaude - (13) 3304-0528", ln=True, align="C")
                            
                            pdf = PDFReceituario()
                            pdf.add_page()
                            pdf.set_auto_page_break(auto=True, margin=30)
                            
                            # Título
                            pdf.set_font("Helvetica", "B", 18)
                            pdf.set_text_color(*COR_ROSA)
                            pdf.cell(0, 10, "RECEITUÁRIO", ln=True, align="C")
                            pdf.ln(5)
                            
                            # Linha decorativa
                            pdf.set_draw_color(*COR_ROSA)
                            pdf.set_line_width(0.5)
                            pdf.line(60, pdf.get_y(), 150, pdf.get_y())
                            pdf.ln(10)
                            
                            # Dados do paciente
                            pdf.set_font("Helvetica", "B", 12)
                            pdf.set_text_color(*COR_TEXTO)
                            pdf.cell(0, 8, f"{data_rec.strftime('%d/%m/%Y')}", ln=True)
                            pdf.cell(0, 8, f"{cliente.nome}", ln=True)
                            pdf.ln(8)
                            
                            # Título do conteúdo
                            pdf.set_font("Helvetica", "B", 11)
                            pdf.set_text_color(*COR_ROSA)
                            pdf.cell(0, 8, "INDICAÇÃO DE TRATAMENTO", ln=True)
                            pdf.ln(3)
                            
                            # Conteúdo do receituário
                            pdf.set_font("Helvetica", "", 11)
                            pdf.set_text_color(*COR_TEXTO)
                            pdf.multi_cell(0, 7, receituario_txt)
                            
                            pdf_bytes = bytes(pdf.output())
                            
                            # Download automático do PDF
                            st.download_button(
                                label="📥 PDF gerado! Clique para baixar",
                                data=pdf_bytes,
                                file_name=f"receituario_{cliente.nome.replace(' ', '_')}_{data_rec.strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key="rec_popup_download"
                            )
                        except Exception as e:
                            st.error(f"Erro ao gerar PDF: {e}")
            else:
                st.info("Selecione um cliente para continuar.")
        finally:
            db.close()
    _abrir()


def _modal_receituario(cliente_id=None, cliente_nome=None, receituario_texto=None):
    @st.dialog("Receituário", width="large")
    def _abrir():
        # Usa valores passados ou busca no session_state como fallback
        cliente_at_id = cliente_id or st.session_state.get("atendimento_cliente_id")
        cliente_at_nome = cliente_nome or st.session_state.get("atendimento_cliente_nome", "")
        receituario_txt = receituario_texto or st.session_state.get("at_receituario_val", "")
        
        if not cliente_at_id:
            st.error("Selecione uma cliente primeiro.")
            if st.button("Fechar", use_container_width=True, key="rec_fechar_err"):
                st.rerun()
            return
        
        if not receituario_txt or str(receituario_txt).strip() == "":
            st.warning("Nenhum receituário preenchido para este atendimento.")
            if st.button("Fechar", use_container_width=True, key="rec_fechar_vazio"):
                st.rerun()
            return
        
        st.markdown(f"**Paciente:** {cliente_at_nome}")
        st.markdown(f"**Data:** {_hoje().strftime('%d/%m/%Y')}")
        st.markdown("---")
        st.markdown("### Receituário (Indicação de Tratamento)")
        st.markdown(receituario_txt)
        
        # Gerar PDF
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # Logo (tenta carregar se existir)
            try:
                logo_path = os.path.join(os.path.dirname(__file__), "assets", "logogf.png")
                if os.path.exists(logo_path):
                    pdf.image(logo_path, x=10, y=10, w=40)
                    pdf.ln(25)
            except:
                pdf.ln(10)
            
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "GABRIELA FRANCO SAÚDE INTEGRATIVA", ln=True, align="C")
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 8, "Receituário", ln=True, align="C")
            pdf.ln(6)
            
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, f"Paciente: {cliente_at_nome}", ln=True)
            pdf.cell(0, 7, f"Data: {_hoje().strftime('%d/%m/%Y')}", ln=True)
            pdf.ln(4)
            
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Receituário (Indicação de Tratamento):", ln=True)
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 7, str(receituario_txt))
            
            pdf_bytes = bytes(pdf.output())
            
            st.download_button(
                "⬇️ Baixar PDF",
                data=pdf_bytes,
                file_name=f"receituario_{cliente_at_nome.replace(' ', '_')}_{_hoje().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="rec_download"
            )
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")
        
        if st.button("Fechar", use_container_width=True, key="rec_fechar"):
            st.rerun()
    _abrir()


def _modal_tabela_doses():
    @st.dialog("Tabela de Doses", width="large")
    def _abrir():
        db = SessionLocal()
        try:
            # Busca cliente
            clientes = db.query(Client).order_by(Client.nome.asc()).all()
            mapa_cli = {f"{c.nome} ({c.cpf or ''})": c.id for c in clientes}
            opcoes_cli = ["— selecione —"] + list(mapa_cli.keys())
            
            cliente_sel = st.selectbox("Cliente", opcoes_cli, key="dose_cliente")
            cliente_id = mapa_cli.get(cliente_sel) if cliente_sel != "— selecione —" else None
            
            col1, col2, col3 = st.columns(3)
            with col1:
                medicacao = st.text_input("Medicação", key="dose_medicacao")
                semana = st.text_input("Semana", key="dose_semana")
            with col2:
                dose = st.text_input("Dose", key="dose_dose")
                via = st.text_input("Via", key="dose_via")
            with col3:
                peso = st.number_input("Peso (kg)", min_value=0.0, step=0.1, key="dose_peso")
                data_dose = st.date_input("Data", value=_hoje(), key="dose_data")
            
            if st.button("➕ Adicionar à tabela", use_container_width=True, key="dose_add"):
                if not cliente_id:
                    st.error("Selecione um cliente.")
                elif not medicacao:
                    st.error("Informe a medicação.")
                else:
                    nova_dose = DoseTable(
                        cliente_id=cliente_id,
                        medicacao=medicacao,
                        semana=semana,
                        dose=dose,
                        via=via,
                        peso=peso,
                        data_registro=data_dose
                    )
                    db.add(nova_dose)
                    db.commit()
                    st.success("Dose registrada!")
                    st.rerun()
            
            # Mostrar tabela existente
            st.markdown("---")
            st.markdown("### Doses registradas")
            
            if cliente_id:
                doses = db.query(DoseTable).filter(
                    DoseTable.cliente_id == cliente_id
                ).order_by(DoseTable.criado_em.desc()).all()
                
                if doses:
                    dados = [{
                        "Data": d.data_registro.strftime("%d/%m/%Y") if d.data_registro else "—",
                        "Medicação": d.medicacao,
                        "Semana": d.semana or "—",
                        "Dose": d.dose or "—",
                        "Via": d.via or "—",
                        "Peso": f"{d.peso} kg" if d.peso else "—",
                    } for d in doses]
                    st.dataframe(pd.DataFrame(dados), use_container_width=True, hide_index=True)
                    
                    # Botão PDF sempre visível quando há cliente selecionado
                    st.markdown("---")
                    if st.button("📄 Gerar PDF da tabela", use_container_width=True, key="dose_pdf"):
                        try:
                            from fpdf import FPDF
                            import os
                            
                            # Cores do sistema
                            COR_ROSA = (213, 156, 156)
                            COR_ROSA_CLARO = (255, 240, 238)
                            COR_BRANCO = (255, 255, 255)
                            COR_TEXTO = (74, 48, 48)
                            
                            class PDFTabelaDoses(FPDF):
                                def header(self):
                                    self.set_fill_color(*COR_ROSA_CLARO)
                                    self.rect(0, 0, 210, 297, 'F')
                                    self.set_fill_color(245, 220, 220)
                                    self.rect(0, 0, 210, 60, 'F')
                                    try:
                                        possiveis_caminhos = [
                                            os.path.join(os.path.dirname(__file__), "ui", "logogf.png"),
                                            os.path.join(os.path.dirname(__file__), "assets", "logogf.png"),
                                        ]
                                        for caminho in possiveis_caminhos:
                                            if os.path.exists(caminho):
                                                self.image(caminho, x=75, y=20, w=60)
                                                break
                                    except:
                                        pass
                                    self.ln(55)
                                
                                def footer(self):
                                    self.set_y(-25)
                                    self.set_fill_color(*COR_ROSA)
                                    self.rect(0, self.get_y(), 210, 25, 'F')
                                    self.set_y(-20)
                                    self.set_font("Helvetica", "", 9)
                                    self.set_text_color(*COR_BRANCO)
                                    self.cell(0, 5, "Praça São Judas Tadeu, 160 - Jardim Casqueiro - Cubatão", ln=True, align="C")
                                    self.cell(0, 5, "@gabifrancosaude - (13) 3304-0528", ln=True, align="C")
                            
                            pdf = PDFTabelaDoses()
                            pdf.add_page()
                            pdf.set_auto_page_break(auto=True, margin=30)
                            
                            cli = db.get(Client, cliente_id)
                            
                            # Título
                            pdf.set_font("Helvetica", "B", 18)
                            pdf.set_text_color(*COR_ROSA)
                            pdf.cell(0, 10, "TABELA DE DOSES", ln=True, align="C")
                            pdf.ln(8)
                            
                            # Dados do paciente
                            pdf.set_font("Helvetica", "B", 12)
                            pdf.set_text_color(*COR_ROSA)
                            nome_pac = cli.nome if cli else 'N/A'
                            pdf.cell(pdf.get_string_width("Paciente: ") + 2, 8, "Paciente: ", 0, 0)
                            pdf.set_text_color(0, 0, 0)
                            pdf.cell(0, 8, nome_pac, ln=True)
                            pdf.set_font("Helvetica", "", 10)
                            pdf.set_text_color(*COR_ROSA)
                            pdf.cell(pdf.get_string_width("Data: ") + 2, 6, "Data: ", 0, 0)
                            pdf.set_text_color(0, 0, 0)
                            from datetime import datetime as _dt
                            pdf.cell(0, 6, _dt.now().strftime("%d/%m/%Y"), ln=True)
                            pdf.ln(6)
                            
                            # Tabela
                            pdf.set_draw_color(*COR_ROSA)
                            pdf.set_font("Helvetica", "B", 10)
                            pdf.set_fill_color(*COR_ROSA)
                            pdf.set_text_color(*COR_BRANCO)
                            pdf.cell(35, 8, "Data", 1, 0, 'C', True)
                            pdf.cell(40, 8, "Medicação", 1, 0, 'C', True)
                            pdf.cell(25, 8, "Semana", 1, 0, 'C', True)
                            pdf.cell(30, 8, "Dose", 1, 0, 'C', True)
                            pdf.cell(25, 8, "Via", 1, 0, 'C', True)
                            pdf.cell(25, 8, "Peso", 1, 0, 'C', True)
                            pdf.ln()
                            
                            pdf.set_font("Helvetica", "", 9)
                            pdf.set_text_color(*COR_TEXTO)
                            for d in doses:
                                pdf.cell(35, 8, d.data_registro.strftime("%d/%m/%Y") if d.data_registro else "—", 1)
                                pdf.cell(40, 8, d.medicacao[:18], 1)
                                pdf.cell(25, 8, (d.semana or "—")[:10], 1)
                                pdf.cell(30, 8, (d.dose or "—")[:12], 1)
                                pdf.cell(25, 8, (d.via or "—")[:10], 1)
                                pdf.cell(25, 8, f"{d.peso} kg" if d.peso else "—", 1)
                                pdf.ln()
                            
                            pdf_bytes = bytes(pdf.output())
                            import base64
                            b64_pdf = base64.b64encode(pdf_bytes).decode()
                            col_dl, col_view = st.columns(2)
                            with col_dl:
                                st.download_button(
                                    "⬇️ Baixar PDF",
                                    data=pdf_bytes,
                                    file_name=f"tabela_doses_{cli.nome.replace(' ', '_') if cli else 'cliente'}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key="dose_download"
                                )
                            with col_view:
                                st.markdown(f'<a href="data:application/pdf;base64,{b64_pdf}" target="_blank" style="display:inline-block;width:100%;text-align:center;padding:0.5rem 1rem;background:#d59c9c;color:white;border-radius:8px;text-decoration:none;font-weight:600;">📤 Abrir / Compartilhar</a>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Erro ao gerar PDF: {e}")
                else:
                    st.info("Nenhuma dose registrada para este cliente.")
                    # Botão PDF mesmo sem doses - mostra tabela vazia
                    st.markdown("---")
                    if st.button("📄 Gerar PDF (tabela vazia)", use_container_width=True, key="dose_pdf_vazio"):
                        try:
                            from fpdf import FPDF
                            import os
                            
                            # Cores do sistema
                            COR_ROSA = (213, 156, 156)
                            COR_ROSA_CLARO = (255, 240, 238)
                            COR_BRANCO = (255, 255, 255)
                            COR_TEXTO = (74, 48, 48)
                            
                            class PDFTabelaDoses(FPDF):
                                def header(self):
                                    self.set_fill_color(*COR_ROSA_CLARO)
                                    self.rect(0, 0, 210, 297, 'F')
                                    self.set_fill_color(245, 220, 220)
                                    self.rect(0, 0, 210, 60, 'F')
                                    try:
                                        possiveis_caminhos = [
                                            os.path.join(os.path.dirname(__file__), "ui", "logogf.png"),
                                            os.path.join(os.path.dirname(__file__), "assets", "logogf.png"),
                                        ]
                                        for caminho in possiveis_caminhos:
                                            if os.path.exists(caminho):
                                                self.image(caminho, x=75, y=20, w=60)
                                                break
                                    except:
                                        pass
                                    self.ln(55)
                                
                                def footer(self):
                                    self.set_y(-25)
                                    self.set_fill_color(*COR_ROSA)
                                    self.rect(0, self.get_y(), 210, 25, 'F')
                                    self.set_y(-20)
                                    self.set_font("Helvetica", "", 9)
                                    self.set_text_color(*COR_BRANCO)
                                    self.cell(0, 5, "Praça São Judas Tadeu, 160 - Jardim Casqueiro - Cubatão", ln=True, align="C")
                                    self.cell(0, 5, "@gabifrancosaude - (13) 3304-0528", ln=True, align="C")
                            
                            pdf = PDFTabelaDoses()
                            pdf.add_page()
                            pdf.set_auto_page_break(auto=True, margin=30)
                            
                            cli = db.get(Client, cliente_id)
                            
                            # Título
                            pdf.set_font("Helvetica", "B", 18)
                            pdf.set_text_color(*COR_ROSA)
                            pdf.cell(0, 10, "TABELA DE DOSES", ln=True, align="C")
                            pdf.ln(8)
                            
                            # Dados do paciente
                            pdf.set_font("Helvetica", "B", 12)
                            pdf.set_text_color(*COR_ROSA)
                            nome_pac = cli.nome if cli else 'N/A'
                            pdf.cell(pdf.get_string_width("Paciente: ") + 2, 8, "Paciente: ", 0, 0)
                            pdf.set_text_color(0, 0, 0)
                            pdf.cell(0, 8, nome_pac, ln=True)
                            pdf.set_font("Helvetica", "", 10)
                            pdf.set_text_color(*COR_ROSA)
                            pdf.cell(pdf.get_string_width("Data: ") + 2, 6, "Data: ", 0, 0)
                            pdf.set_text_color(0, 0, 0)
                            from datetime import datetime as _dt
                            pdf.cell(0, 6, _dt.now().strftime("%d/%m/%Y"), ln=True)
                            pdf.ln(6)
                            
                            # Tabela
                            pdf.set_draw_color(*COR_ROSA)
                            pdf.set_font("Helvetica", "B", 10)
                            pdf.set_fill_color(*COR_ROSA)
                            pdf.set_text_color(*COR_BRANCO)
                            pdf.cell(35, 8, "Data", 1, 0, 'C', True)
                            pdf.cell(40, 8, "Medicação", 1, 0, 'C', True)
                            pdf.cell(25, 8, "Semana", 1, 0, 'C', True)
                            pdf.cell(30, 8, "Dose", 1, 0, 'C', True)
                            pdf.cell(25, 8, "Via", 1, 0, 'C', True)
                            pdf.cell(25, 8, "Peso", 1, 0, 'C', True)
                            pdf.ln()
                            
                            pdf.set_font("Helvetica", "", 9)
                            pdf.set_text_color(*COR_TEXTO)
                            pdf.cell(0, 8, "Nenhuma dose registrada.", ln=True, align="C")
                            
                            pdf_bytes = bytes(pdf.output())
                            import base64 as _b64v
                            b64_pdf_v = _b64v.b64encode(pdf_bytes).decode()
                            col_dl2, col_view2 = st.columns(2)
                            with col_dl2:
                                st.download_button(
                                    "⬇️ Baixar PDF",
                                    data=pdf_bytes,
                                    file_name=f"tabela_doses_{cli.nome.replace(' ', '_') if cli else 'cliente'}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key="dose_download_vazio"
                                )
                            with col_view2:
                                st.markdown(f'<a href="data:application/pdf;base64,{b64_pdf_v}" target="_blank" style="display:inline-block;width:100%;text-align:center;padding:0.5rem 1rem;background:#d59c9c;color:white;border-radius:8px;text-decoration:none;font-weight:600;">📤 Abrir / Compartilhar</a>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Erro ao gerar PDF: {e}")
            else:
                st.info("Selecione um cliente para ver as doses.")
        finally:
            db.close()
    _abrir()


# ====== TELA: ATENDIMENTOS ======
def tela_atendimentos():
    header_titulo("Atendimentos", "Baixa automática no estoque")
    db = SessionLocal()
    try:
        st.markdown("### Cliente")

        # Buscar todos os clientes para o selectbox
        clientes = db.query(Client).order_by(Client.nome.asc()).all()
        mapa_clientes = {f"{c.nome} (CPF: {c.cpf or '-'})": c for c in clientes}

        sel_at = st.selectbox(
            "Selecione a cliente",
            options=["— Selecione —"] + list(mapa_clientes.keys()),
            key="atendimento_selectbox",
        )

        cliente_at_id = None
        cliente_at_nome = ""

        if sel_at and sel_at != "— Selecione —":
            cliente_selecionado = mapa_clientes.get(sel_at)
            if cliente_selecionado:
                cliente_at_id = cliente_selecionado.id
                cliente_at_nome = cliente_selecionado.nome
                st.session_state["atendimento_cliente_id"] = cliente_at_id
                st.session_state["atendimento_cliente_nome"] = cliente_at_nome

        if cliente_at_nome:
            st.info(f"Cliente selecionada: **{cliente_at_nome}**")

        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            data_at = st.date_input("Data", value=_hoje(), format="DD/MM/YYYY", key="at_data")
            queixa = st.text_area("Queixa da consulta", key="at_queixa")
        with col2:
            # Lista suspensa de tratamentos cadastrados
            tratamentos_lista = db.query(Tratamento).filter(Tratamento.ativo == True).order_by(Tratamento.nome.asc()).all()
            opcoes_trat = ["— selecione —"] + [t.nome for t in tratamentos_lista]
            tipo = st.selectbox("Tipo de tratamento realizado", opcoes_trat, key="at_tipo")
            if tipo == "— selecione —":
                tipo = ""
            protocolo = st.text_area("Protocolo de atendimento", key="at_protocolo")

        obs = st.text_area("Observações", key="at_obs")

        # Botões de ação extras
        col_rec, col_dose = st.columns(2)
        with col_rec:
            if st.button("📄 Gerar Receituário", use_container_width=True, key="btn_receituario"):
                _modal_receituario_popup()
        with col_dose:
            if st.button("💉 Tabela de Doses", use_container_width=True, key="btn_doses"):
                _modal_tabela_doses()

        st.markdown("---")
        st.markdown("#### Materiais usados")

        # Buscar materiais cadastrados + produtos do estoque
        mats_cadastrados = db.query(Material).filter(Material.ativo == True).order_by(Material.nome.asc()).all()
        produtos = db.query(Product).order_by(Product.nome.asc()).all()
        mapa_prod = {p.nome: p.id for p in produtos}
        # Lista de nomes para seleção: materiais cadastrados + produtos do estoque
        nomes_materiais = sorted(set([m.nome for m in mats_cadastrados] + list(mapa_prod.keys())))

        linhas = st.number_input("Quantos produtos diferentes foram usados?", min_value=0, step=1, value=0)
        materiais = []

        for i in range(int(linhas)):
            c1, c2, c3 = st.columns([3, 2, 1])
            with c1:
                prod_nome = st.selectbox(
                    f"Material {i + 1}",
                    ["— selecione —"] + nomes_materiais,
                    key=f"at_prod_{i}",
                )
            with c2:
                lote_opcoes = ["— selecione —"]
                lote_map = {}
                if prod_nome and prod_nome != "— selecione —" and prod_nome in mapa_prod:
                    lotes_disp = (
                        db.query(StockLote)
                        .filter(
                            StockLote.produto_id == mapa_prod[prod_nome],
                            StockLote.quantidade_atual > 0,
                        )
                        .all()
                    )
                    for lt in lotes_disp:
                        label = f"Lote: {lt.lote or 'S/N'} | Qtd: {lt.quantidade_atual}"
                        lote_opcoes.append(label)
                        lote_map[label] = lt.id
                lote_sel = st.selectbox(f"Lote {i + 1}", lote_opcoes, key=f"at_lote_{i}")
            with c3:
                qtd = st.number_input("Qtd", min_value=0, step=1, key=f"at_qtd_{i}")

            if (
                prod_nome and prod_nome != "— selecione —"
                and lote_sel and lote_sel != "— selecione —"
                and lote_sel in lote_map
                and qtd > 0
            ):
                materiais.append((lote_map[lote_sel], mapa_prod[prod_nome], qtd))

        if st.button("Salvar atendimento", use_container_width=True):
            if not cliente_at_id:
                st.error("Selecione uma cliente.")
            else:
                ap = Appointment(
                    data=data_at,
                    mes=month_from_date(data_at),
                    cliente_id=cliente_at_id,
                    queixa_consulta=queixa,
                    protocolo_atendimento=protocolo,
                    tipo_tratamento=tipo,
                    retorno_indicado=None,
                    receituario=None,
                    observacoes=obs,
                )
                db.add(ap)
                db.commit()

                for (lote_id, prod_id, qtd) in materiais:
                    am = AppointmentMaterial(
                        atendimento_id=ap.id,
                        lote_id=lote_id,
                        produto_id=prod_id,
                        quantidade=float(qtd),
                    )
                    db.add(am)
                    db.commit()
                    try:
                        movimentar(lote_id, "saida", float(qtd), motivo=f"Atendimento #{ap.id}")
                    except Exception as e:
                        st.warning(f"Falha na baixa do lote {lote_id}: {e}")

                st.session_state.pop("atendimento_cliente_id", None)
                st.session_state.pop("atendimento_cliente_nome", None)
                # Limpar campos do formulário
                for key in ["atendimento_selectbox", "at_data", "at_queixa", "at_tipo", "at_protocolo", "at_obs"]:
                    if key in st.session_state:
                        st.session_state.pop(key, None)
                st.success("Atendimento salvo e estoque atualizado.")
                st.rerun()

        st.markdown("---")
        st.markdown("### Histórico de Atendimentos")

        # Filtro de datas
        col_filtro1, col_filtro2, col_filtro3, col_filtro4, col_filtro5 = st.columns([2, 2, 1, 1, 1])
        with col_filtro1:
            data_inicio = st.date_input("Data início", value=_hoje() - timedelta(days=30), key="at_hist_inicio")
        with col_filtro2:
            data_fim = st.date_input("Data fim", value=_hoje(), key="at_hist_fim")
        with col_filtro3:
            st.markdown("<br>", unsafe_allow_html=True)
            filtrar_hoje = st.button("Hoje", key="at_hist_hoje")
        with col_filtro4:
            st.markdown("<br>", unsafe_allow_html=True)
            editar_at_btn = st.button("✏️ Editar", key="at_hist_editar")
        with col_filtro5:
            st.markdown("<br>", unsafe_allow_html=True)
            excluir_at_btn = st.button("🗑️ Excluir", key="at_hist_excluir")

        if filtrar_hoje:
            data_inicio = _hoje()
            data_fim = _hoje()

        # Buscar atendimentos no período
        atendimentos = (
            db.query(Appointment, Client)
            .join(Client, Appointment.cliente_id == Client.id)
            .filter(Appointment.data >= data_inicio)
            .filter(Appointment.data <= data_fim)
            .order_by(Appointment.data.desc(), Appointment.id.desc())
            .all()
        )

        if atendimentos:
            import pandas as pd
            dados_tabela = []
            ids_atendimentos = []
            for at, cli in atendimentos:
                ids_atendimentos.append(at.id)
                dados_tabela.append({
                    "Selecionar": False,
                    "Data": at.data.strftime("%d/%m/%Y") if at.data else "—",
                    "Cliente": cli.nome if cli else "—",
                    "Protocolo": (at.protocolo_atendimento[:50] + "...") if at.protocolo_atendimento and len(at.protocolo_atendimento) > 50 else (at.protocolo_atendimento or "—"),
                    "Queixa": (at.queixa_consulta[:50] + "...") if at.queixa_consulta and len(at.queixa_consulta) > 50 else (at.queixa_consulta or "—"),
                    "Tipo Tratamento": at.tipo_tratamento or "—",
                    "Observações": (at.observacoes[:50] + "...") if at.observacoes and len(at.observacoes) > 50 else (at.observacoes or "—"),
                })

            df_hist = pd.DataFrame(dados_tabela)
            edited_df = st.data_editor(
                df_hist,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False),
                },
                disabled=["Data", "Cliente", "Protocolo", "Queixa", "Tipo Tratamento", "Observações"],
                key="at_hist_editor"
            )

            # Identificar linha selecionada
            selecionados = edited_df[edited_df["Selecionar"] == True]
            if len(selecionados) > 1:
                st.warning("Selecione apenas 1 atendimento por vez.")
            elif len(selecionados) == 1:
                idx_selecionado = selecionados.index[0]
                at_id_selecionado = ids_atendimentos[idx_selecionado]

                if excluir_at_btn:
                    at_del = db.query(Appointment).filter(Appointment.id == at_id_selecionado).first()
                    if at_del:
                        db.delete(at_del)
                        db.commit()
                        st.success("Atendimento excluído com sucesso!")
                        st.rerun()

                if editar_at_btn:
                    st.session_state["editar_atendimento_id"] = at_id_selecionado
                    st.rerun()
            else:
                if editar_at_btn or excluir_at_btn:
                    st.warning("Selecione um atendimento na tabela primeiro.")

            # Modal de edição
            if "editar_atendimento_id" in st.session_state:
                at_edit = db.query(Appointment).filter(Appointment.id == st.session_state["editar_atendimento_id"]).first()
                if at_edit:
                    st.markdown("---")
                    st.markdown("#### Editar Atendimento")
                    with st.form("form_editar_atendimento", clear_on_submit=False):
                        edit_data = st.date_input("Data", value=at_edit.data, format="DD/MM/YYYY")
                        edit_queixa = st.text_area("Queixa", value=at_edit.queixa_consulta or "")
                        edit_tipo = st.text_input("Tipo Tratamento", value=at_edit.tipo_tratamento or "")
                        edit_obs = st.text_area("Observações", value=at_edit.observacoes or "")
                        col_salvar, col_cancelar = st.columns(2)
                        with col_salvar:
                            salvar_edicao = st.form_submit_button("Salvar", use_container_width=True)
                        with col_cancelar:
                            cancelar_edicao = st.form_submit_button("Cancelar", use_container_width=True)

                    if salvar_edicao:
                        at_edit.data = edit_data
                        at_edit.queixa_consulta = edit_queixa
                        at_edit.tipo_tratamento = edit_tipo
                        at_edit.observacoes = edit_obs
                        db.commit()
                        st.success("Atendimento atualizado!")
                        st.session_state.pop("editar_atendimento_id", None)
                        st.rerun()
                    if cancelar_edicao:
                        st.session_state.pop("editar_atendimento_id", None)
                        st.rerun()
        else:
            st.info("Nenhum atendimento encontrado no período selecionado.")

    finally:
        db.close()


# ====== TELA: BIOMETRIA ======
def tela_biometria():
    header_titulo("Biometria", "Evolução automática e gráficos")
    db = SessionLocal()
    try:
        clientes = db.query(Client).order_by(Client.nome.asc()).all()
        mapa = {f"{c.nome} ({c.cpf})": c.id for c in clientes}

        col_cli, col_data = st.columns(2)
        with col_cli:
            cliente_sel = st.selectbox("Cliente", list(mapa.keys()) if mapa else ["—"])
        with col_data:
            data_m = st.date_input("Data da medição", value=_hoje(), format="DD/MM/YYYY")

        if cliente_sel and cliente_sel != "—":
            cid = mapa[cliente_sel]

            col1, col2, col3 = st.columns(3)
            with col1:
                peso = st.number_input("Peso (kg)", min_value=0.0, step=1.0)
                cintura = st.number_input("Cintura (cm)", min_value=0.0, step=1.0)
            with col2:
                abdomen = st.number_input("Abdômen (cm)", min_value=0.0, step=1.0)
                quadril = st.number_input("Quadril (cm)", min_value=0.0, step=1.0)
            with col3:
                braco = st.number_input("Braço (cm)", min_value=0.0, step=1.0)
                coxa = st.number_input("Coxa (cm)", min_value=0.0, step=1.0)

            if st.button("Salvar medidas"):
                b = Biometrics(
                    cliente_id=cid,
                    data_medicao=data_m,
                    peso=peso,
                    cintura=cintura,
                    abdomen=abdomen,
                    quadril=quadril,
                    braco=braco,
                    coxa=coxa,
                )
                db.add(b)
                db.commit()
                st.success("Medidas salvas.")

            historico = pd.read_sql(
                db.query(Biometrics)
                .filter(Biometrics.cliente_id == cid)
                .order_by(Biometrics.data_medicao.asc())
                .statement,
                db.bind,
            )

            if not historico.empty:
                st.markdown("#### Evolução de peso")
                chart = alt.Chart(historico).mark_line(point=True).encode(
                    x="data_medicao:T", y="peso:Q"
                )
                st.altair_chart(chart, use_container_width=True)

                historico["data_medicao"] = (
                    pd.to_datetime(historico["data_medicao"], errors="coerce")
                    .dt.strftime("%d/%m/%Y")
                )
                st.markdown("#### Histórico completo")
                bio_records = (
                    db.query(Biometrics)
                    .filter(Biometrics.cliente_id == cid)
                    .order_by(Biometrics.data_medicao.desc())
                    .all()
                )
                for _bio in bio_records:
                    _data_bio = _bio.data_medicao.strftime("%d/%m/%Y") if _bio.data_medicao else "—"
                    col_bio_info, col_bio_menu = st.columns([6, 0.4])
                    with col_bio_info:
                        st.write(
                            f"**{_data_bio}** — Peso: {_bio.peso or '—'} kg | "
                            f"Cintura: {_bio.cintura or '—'} | Abdômen: {_bio.abdomen or '—'} | "
                            f"Quadril: {_bio.quadril or '—'} | Braço: {_bio.braco or '—'} | "
                            f"Coxa: {_bio.coxa or '—'}"
                        )
                    with col_bio_menu:
                        with st.popover("⋮", use_container_width=True):
                            if st.button("✏️ Editar", key=f"bio_edit_{_bio.id}"):
                                st.session_state["bio_editando"] = _bio.id
                                st.rerun()
                            if st.button("🗑️ Excluir", key=f"bio_del_{_bio.id}"):
                                db.delete(_bio)
                                db.commit()
                                st.rerun()
                # Formulário de edição de biometria
                if st.session_state.get("bio_editando"):
                    _bid = st.session_state["bio_editando"]
                    _bio_ed = db.get(Biometrics, _bid)
                    if _bio_ed and _bio_ed.cliente_id == cid:
                        st.markdown("---")
                        st.markdown("##### Editar Biometria")
                        with st.form("form_editar_bio", clear_on_submit=False):
                            _ed_bio_data = st.date_input("Data", value=_bio_ed.data_medicao, format="DD/MM/YYYY", key="ed_bio_data")
                            col_eb1, col_eb2, col_eb3 = st.columns(3)
                            with col_eb1:
                                _ed_bio_peso = st.number_input("Peso (kg)", value=float(_bio_ed.peso or 0), min_value=0.0, step=0.1, key="ed_bio_peso")
                                _ed_bio_cin = st.number_input("Cintura (cm)", value=float(_bio_ed.cintura or 0), min_value=0.0, step=0.1, key="ed_bio_cin")
                            with col_eb2:
                                _ed_bio_abd = st.number_input("Abdômen (cm)", value=float(_bio_ed.abdomen or 0), min_value=0.0, step=0.1, key="ed_bio_abd")
                                _ed_bio_qua = st.number_input("Quadril (cm)", value=float(_bio_ed.quadril or 0), min_value=0.0, step=0.1, key="ed_bio_qua")
                            with col_eb3:
                                _ed_bio_bra = st.number_input("Braço (cm)", value=float(_bio_ed.braco or 0), min_value=0.0, step=0.1, key="ed_bio_bra")
                                _ed_bio_cox = st.number_input("Coxa (cm)", value=float(_bio_ed.coxa or 0), min_value=0.0, step=0.1, key="ed_bio_cox")
                            col_ebsv, col_ebcn = st.columns(2)
                            with col_ebsv:
                                _salvar_bio_ed = st.form_submit_button("💾 Salvar", use_container_width=True)
                            with col_ebcn:
                                _cancelar_bio_ed = st.form_submit_button("Cancelar", use_container_width=True)
                        if _salvar_bio_ed:
                            _bio_ed.data_medicao = _ed_bio_data
                            _bio_ed.peso = _ed_bio_peso
                            _bio_ed.cintura = _ed_bio_cin
                            _bio_ed.abdomen = _ed_bio_abd
                            _bio_ed.quadril = _ed_bio_qua
                            _bio_ed.braco = _ed_bio_bra
                            _bio_ed.coxa = _ed_bio_cox
                            db.commit()
                            st.success("Biometria atualizada!")
                            st.session_state.pop("bio_editando", None)
                            st.rerun()
                        if _cancelar_bio_ed:
                            st.session_state.pop("bio_editando", None)
                            st.rerun()
    finally:
        db.close()


# ====== TELA: ESTOQUE ======
def tela_estoque():
    header_titulo("Estoque", "Produtos, lotes e movimentações")
    db = SessionLocal()
    try:
        aba1, aba2 = st.tabs(["Estoque", "Movimentações"])

        # ---------- ABA 1: Estoque ----------
        with aba1:
            st.markdown("### Registrar nova compra (entrada de lote)")
            produtos = db.query(Product).order_by(Product.nome.asc()).all()
            mapa_prod = {p.nome: p.id for p in produtos}

            with st.form("form_nova_compra", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    prod_compra = st.selectbox(
                        "Produto*",
                        ["— selecione —"] + list(mapa_prod.keys()),
                    )
                    lote_compra = st.text_input("Lote")
                    qtd_compra = st.number_input("Quantidade", min_value=0.0, step=1.0)
                    qtd_min_compra = st.number_input("Quantidade mínima", min_value=0.0, step=1.0)
                with col2:
                    validade_compra = st.date_input("Data de validade", value=_hoje(), format="DD/MM/YYYY")
                    fornecedor_compra = st.text_input("Fornecedor")
                    data_ent_compra = st.date_input("Data de entrada", value=_hoje(), format="DD/MM/YYYY")

                salvar_compra = st.form_submit_button("Registrar compra", use_container_width=True)

            if salvar_compra:
                if prod_compra == "— selecione —" or qtd_compra <= 0:
                    st.error("Selecione um produto e informe quantidade.")
                else:
                    novo_lote = StockLote(
                        produto_id=mapa_prod[prod_compra],
                        lote=lote_compra or None,
                        quantidade_atual=qtd_compra,
                        quantidade_minima=0,
                        data_validade=validade_compra,
                        fornecedor=fornecedor_compra or None,
                        data_entrada=data_ent_compra,
                    )
                    db.add(novo_lote)
                    db.commit()
                    movimentar(novo_lote.id, "entrada", qtd_compra, motivo="Compra registrada")
                    st.success("Lote registrado!")
                    st.rerun()

            st.markdown("---")
            st.markdown("### Estoque atual")

            # Filtro por categoria
            _categorias_est = ["Todas"] + sorted(list(set(p.categoria for p in db.query(Product).all() if p.categoria)))
            _cat_filtro = st.selectbox("Filtrar por categoria", _categorias_est, key="est_filtro_cat")

            lotes = (
                db.query(StockLote)
                .join(Product)
                .order_by(Product.nome.asc(), StockLote.data_validade.asc())
                .all()
            )
            
            # Aplicar filtro
            if _cat_filtro != "Todas":
                lotes = [lt for lt in lotes if lt.produto and lt.produto.categoria == _cat_filtro]
            
            if lotes:
                dados_est = []
                ids_lotes = []
                for lt in lotes:
                    ids_lotes.append(lt.id)
                    # Calcular saldo do produto (entradas - saídas de todas as movimentações)
                    entradas = db.query(func.sum(StockMovement.quantidade)).filter(
                        StockMovement.produto_id == lt.produto_id,
                        StockMovement.tipo == "entrada"
                    ).scalar() or 0
                    saidas = db.query(func.sum(StockMovement.quantidade)).filter(
                        StockMovement.produto_id == lt.produto_id,
                        StockMovement.tipo == "saida"
                    ).scalar() or 0
                    saldo_produto = float(entradas) - float(saidas)
                    
                    dados_est.append({
                        "Selecionar": False,
                        "Produto": lt.produto.nome if lt.produto else "—",
                        "Categoria": lt.produto.categoria if lt.produto else "—",
                        "Lote": lt.lote or "S/N",
                        "Qtd Comprada": lt.quantidade_atual,
                        "Saldo": round(saldo_produto, 2),
                        "Validade": formatar_data_br(lt.data_validade),
                        "Fornecedor": lt.fornecedor or "",
                    })
                
                df_est = pd.DataFrame(dados_est)
                edited_df_est = st.data_editor(
                    df_est,
                    hide_index=True,
                    column_config={"Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False)},
                    disabled=["Produto", "Categoria", "Lote", "Quantidade", "Validade", "Fornecedor"],
                    key="est_editor"
                )
                
                # Identificar linha selecionada
                linha_sel_est = None
                for i, row in edited_df_est.iterrows():
                    if row.get("Selecionar"):
                        linha_sel_est = ids_lotes[i]
                        break
                
                # Botões de ação
                col_est1, col_est2, col_est3 = st.columns([1, 1, 4])
                with col_est1:
                    btn_editar_est = st.button("✏️ Editar", key="btn_editar_est", disabled=(linha_sel_est is None))
                with col_est2:
                    btn_excluir_est = st.button("🗑️ Excluir", key="btn_excluir_est", disabled=(linha_sel_est is None))
                
                if btn_excluir_est and linha_sel_est:
                    lt_del = db.get(StockLote, linha_sel_est)
                    if lt_del:
                        db.delete(lt_del)
                        db.commit()
                        st.success("Lote excluído!")
                        st.rerun()
                
                if btn_editar_est and linha_sel_est:
                    st.session_state["est_editando"] = linha_sel_est
                    st.rerun()
                
                # Form de edição
                if st.session_state.get("est_editando"):
                    lt_ed = db.get(StockLote, st.session_state["est_editando"])
                    if lt_ed:
                        st.markdown("---")
                        st.markdown("#### ✏️ Editar lote")
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            new_qtd = st.number_input("Quantidade", value=float(lt_ed.quantidade_atual or 0), key="est_ed_qtd")
                            new_val = st.date_input("Validade", value=lt_ed.data_validade, key="est_ed_val")
                        with ec2:
                            new_forn = st.text_input("Fornecedor", value=lt_ed.fornecedor or "", key="est_ed_forn")
                            new_lote = st.text_input("Lote", value=lt_ed.lote or "", key="est_ed_lote")
                        bc1, bc2 = st.columns(2)
                        with bc1:
                            if st.button("💾 Salvar", key="est_save", use_container_width=True):
                                lt_ed.quantidade_atual = new_qtd
                                lt_ed.data_validade = new_val
                                lt_ed.fornecedor = new_forn if new_forn else None
                                lt_ed.lote = new_lote if new_lote else None
                                db.commit()
                                del st.session_state["est_editando"]
                                st.success("Lote atualizado!")
                                st.rerun()
                        with bc2:
                            if st.button("❌ Cancelar", key="est_cancel", use_container_width=True):
                                del st.session_state["est_editando"]
                                st.rerun()
            else:
                st.info("Nenhum lote cadastrado.")

            st.markdown("### Alertas")
            baixo, validadep = alertas()
            if baixo:
                nomes = [f"{prod.nome} (saldo: {sum([l.quantidade_atual or 0 for l in db.query(StockLote).filter(StockLote.produto_id == prod.id).all()])} unidades)" for prod in baixo]
                st.warning(f"Estoque baixo (≤5 unidades): {', '.join(nomes)}")
            if validadep:
                nomes_v = [f"{lt.produto.nome} (lote: {lt.lote or 'S/N'})" for lt in validadep]
                st.warning(f"Validade próxima (30 dias): {', '.join(nomes_v)}")

        # ---------- ABA 2: Movimentações ----------
        with aba2:
            movs_lista = (
                db.query(StockMovement)
                .order_by(StockMovement.criado_em.desc())
                .all()
            )
            if movs_lista:
                for _mov in movs_lista:
                    # Tenta resolver nome do produto pelo lote
                    try:
                        _lt_mov = db.get(StockLote, _mov.lote_id)
                        _prod_nome_mov = _lt_mov.produto.nome if _lt_mov and _lt_mov.produto else "—"
                        _lote_str_mov = _lt_mov.lote or "S/N" if _lt_mov else "—"
                    except Exception:
                        _prod_nome_mov = "—"
                        _lote_str_mov = "—"
                    _data_mov = str(_mov.criado_em)[:10] if _mov.criado_em else "—"
                    col_mov_info, col_mov_del = st.columns([6, 0.4])
                    with col_mov_info:
                        st.write(
                            f"**{_data_mov}** — {_prod_nome_mov} | Lote: {_lote_str_mov} | "
                            f"{_mov.tipo or '—'} | Qtd: {_mov.quantidade} | {_mov.motivo or '—'}"
                        )
                    with col_mov_del:
                        with st.popover("⋮", use_container_width=True):
                            if st.button("🗑️ Excluir", key=f"mov_del_{_mov.id}"):
                                db.delete(_mov)
                                db.commit()
                                st.rerun()
            else:
                st.info("Nenhuma movimentação registrada.")

            st.markdown("### Movimentar manualmente")
            produtos = db.query(Product).order_by(Product.nome.asc()).all()
            mapa_prod2 = {p.nome: p.id for p in produtos}

            col1, col2 = st.columns(2)
            with col1:
                prod_mov = st.selectbox(
                    "Produto",
                    ["— selecione —"] + list(mapa_prod2.keys()),
                    key="mov_prod",
                )
            with col2:
                lote_mov_opcoes = ["— selecione —"]
                lote_mov_map = {}
                if prod_mov and prod_mov != "— selecione —" and prod_mov in mapa_prod2:
                    lts = db.query(StockLote).filter(StockLote.produto_id == mapa_prod2[prod_mov]).all()
                    for lt in lts:
                        label = f"Lote: {lt.lote or 'S/N'} | Qtd: {lt.quantidade_atual}"
                        lote_mov_opcoes.append(label)
                        lote_mov_map[label] = lt.id
                lote_mov_sel = st.selectbox("Lote", lote_mov_opcoes, key="mov_lote")

            tipo_mov = st.selectbox("Tipo", ["entrada", "saida"])
            qtd_mov = st.number_input("Quantidade", min_value=0.0, step=1.0)
            mot_mov = st.text_input("Motivo")

            if st.button("Confirmar movimentação"):
                if (
                    lote_mov_sel
                    and lote_mov_sel != "— selecione —"
                    and lote_mov_sel in lote_mov_map
                    and qtd_mov > 0
                ):
                    try:
                        movimentar(lote_mov_map[lote_mov_sel], tipo_mov, qtd_mov, mot_mov)
                        st.success("Movimentação registrada.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.error("Selecione produto, lote e informe quantidade.")

    finally:
        db.close()


# ====== TELA: RELATÓRIOS ======
def tela_relatorios():
    header_titulo("Relatórios", "Análise, exportações e insights da clínica")
    db = SessionLocal()
    try:
        _data_hoje = _hoje()
        _ini_mes = _data_hoje.replace(day=1)
        aba_analise, aba_vendas, aba_estoque, aba_clientes = st.tabs([
            "📊 Análise Geral", "💰 Vendas", "📦 Estoque", "👤 Clientes"
        ])

        # ══════════════════════════════════════════
        # ABA 1 — ANÁLISE GERAL
        # ══════════════════════════════════════════
        with aba_analise:
            col_di, col_df = st.columns(2)
            with col_di:
                _r_ini = st.date_input("De", value=_ini_mes, key="rel_ini", format="DD/MM/YYYY")
            with col_df:
                _r_fim = st.date_input("Até", value=_data_hoje, key="rel_fim", format="DD/MM/YYYY")

            # ── Totais ───────────────────────────────────────────────
            try:
                _n_at = db.query(Appointment).filter(
                    Appointment.data >= _r_ini, Appointment.data <= _r_fim).count()
            except Exception:
                _n_at = 0
            _n_cli = db.query(Client).count()
            try:
                from models.sale import Sale, SaleItem
                _vendas = db.query(Sale).filter(
                    Sale.data_venda >= str(_r_ini), Sale.data_venda <= str(_r_fim)).all()
                _n_vendas = len(_vendas)
                _val_vendas = sum(float(v.valor_total or 0) for v in _vendas)
            except Exception:
                _n_vendas, _val_vendas = 0, 0.0

            cv1, cv2, cv3, cv4 = st.columns(4)
            cv1.metric("Atendimentos no período", _n_at)
            cv2.metric("Total de clientes", _n_cli)
            cv3.metric("Vendas no período", _n_vendas)
            cv4.metric("Receita no período", f"R$ {_val_vendas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            st.markdown("---")

            # ── Gráfico: atendimentos por mês ───────────────────────
            try:
                _df_at = pd.read_sql(
                    db.query(Appointment).filter(
                        Appointment.data >= _r_ini, Appointment.data <= _r_fim).statement, db.bind)
                if not _df_at.empty and "data" in _df_at.columns:
                    _df_at["mes"] = pd.to_datetime(_df_at["data"], errors="coerce").dt.strftime("%Y-%m")
                    _por_mes = _df_at.groupby("mes").size().reset_index(name="Atendimentos")
                    st.markdown("#### Atendimentos por mês")
                    st.altair_chart(
                        alt.Chart(_por_mes).mark_bar(color="#D59C9C").encode(
                            x=alt.X("mes:O", title="Mês"),
                            y=alt.Y("Atendimentos:Q"),
                            tooltip=["mes", "Atendimentos"],
                        ).properties(height=260),
                        use_container_width=True,
                    )

                    # ── Gráfico: procedimentos/tipo ─────────────────
                    if "tipo_tratamento" in _df_at.columns:
                        _por_tipo = _df_at.groupby("tipo_tratamento").size().reset_index(name="Total")
                        _por_tipo = _por_tipo[_por_tipo["tipo_tratamento"].notna() & (_por_tipo["tipo_tratamento"] != "")]
                        if not _por_tipo.empty:
                            st.markdown("#### Procedimentos por atendimento")
                            st.altair_chart(
                                alt.Chart(_por_tipo).mark_bar(color="#E2B3A5").encode(
                                    x=alt.X("Total:Q"),
                                    y=alt.Y("tipo_tratamento:N", sort="-x", title="Procedimento"),
                                    tooltip=["tipo_tratamento", "Total"],
                                ).properties(height=max(200, len(_por_tipo) * 30)),
                                use_container_width=True,
                            )
            except Exception as _e:
                st.warning(f"Gráfico de atendimentos indisponível: {_e}")

            # ── Gráfico: vendas por mês ──────────────────────────────
            try:
                _df_v = pd.read_sql(
                    db.query(Sale).filter(
                        Sale.data_venda >= str(_r_ini), Sale.data_venda <= str(_r_fim)).statement, db.bind)
                if not _df_v.empty:
                    _df_v["mes"] = pd.to_datetime(_df_v["data_venda"], errors="coerce").dt.strftime("%Y-%m")
                    _vg = _df_v.groupby("mes").agg(
                        Vendas=("id", "count"), Valor=("valor_total", "sum")).reset_index()
                    st.markdown("#### Vendas por mês")
                    _base = alt.Chart(_vg)
                    _bars = _base.mark_bar(color="#D59C9C", opacity=0.85).encode(
                        x=alt.X("mes:O", title="Mês"), y=alt.Y("Vendas:Q"), tooltip=["mes", "Vendas", "Valor"])
                    _line = _base.mark_line(color="#9b5555", strokeWidth=2, point=True).encode(
                        x="mes:O", y=alt.Y("Valor:Q", axis=alt.Axis(title="Valor (R$)")))
                    st.altair_chart(alt.layer(_bars, _line).resolve_scale(y="independent").properties(height=280),
                                    use_container_width=True)
            except Exception as _e:
                st.warning(f"Gráfico de vendas indisponível: {_e}")

            # ── Botão PDF resumo ─────────────────────────────────────
            st.markdown("---")
            if st.button("📄 Gerar Relatório PDF (resumo)", use_container_width=True):
                try:
                    from fpdf import FPDF as _FPDF
                    import os
                    
                    # Cores do sistema
                    _COR_ROSA = (213, 156, 156)
                    _COR_ROSA_CLARO = (255, 240, 238)
                    _COR_BRANCO = (255, 255, 255)
                    _COR_TEXTO = (74, 48, 48)
                    
                    class PDFRelatorio(_FPDF):
                        def header(self):
                            self.set_fill_color(*_COR_ROSA_CLARO)
                            self.rect(0, 0, 210, 297, 'F')
                            self.set_fill_color(*_COR_ROSA)
                            self.rect(0, 0, 210, 60, 'F')
                            logo_carregada = False
                            try:
                                possiveis_caminhos = [
                                    os.path.join(os.path.dirname(__file__), "ui", "logogf.png"),
                                    os.path.join(os.path.dirname(__file__), "assets", "logogf.png"),
                                    "C:\\Users\\joaoz\\Desktop\\sistema GF\\ui\\logogf.png",
                                ]
                                for caminho in possiveis_caminhos:
                                    if os.path.exists(caminho):
                                        self.image(caminho, x=85, y=10, w=40)
                                        logo_carregada = True
                                        break
                            except:
                                pass
                            if not logo_carregada:
                                self.set_y(16)
                                self.set_font("Helvetica", "B", 28)
                                self.set_text_color(*_COR_BRANCO)
                                self.cell(0, 14, "GABRIELA FRANCO", ln=True, align="C")
                                self.set_font("Helvetica", "", 20)
                                self.cell(0, 10, "SAUDE INTEGRATIVA", ln=True, align="C")
                            self.ln(45)
                        
                        def footer(self):
                            self.set_y(-25)
                            self.set_fill_color(*_COR_ROSA)
                            self.rect(0, self.get_y(), 210, 25, 'F')
                            self.set_y(-20)
                            self.set_font("Helvetica", "", 9)
                            self.set_text_color(*_COR_BRANCO)
                            self.cell(0, 5, "Praça São Judas Tadeu, 160 - Jardim Casqueiro - Cubatão", ln=True, align="C")
                            self.cell(0, 5, "@gabifrancosaude - (13) 3304-0528", ln=True, align="C")
                    
                    _pdf = PDFRelatorio()
                    _pdf.add_page()
                    _pdf.set_auto_page_break(auto=True, margin=30)
                    
                    # Título
                    _pdf.set_font("Helvetica", "B", 18)
                    _pdf.set_text_color(*_COR_ROSA)
                    _pdf.cell(0, 10, "RELATÓRIO GERAL", ln=True, align="C")
                    _pdf.ln(5)
                    
                    # Linha decorativa
                    _pdf.set_draw_color(*_COR_ROSA)
                    _pdf.set_line_width(0.5)
                    _pdf.line(60, _pdf.get_y(), 150, _pdf.get_y())
                    _pdf.ln(10)
                    
                    # Período
                    _pdf.set_font("Helvetica", "B", 12)
                    _pdf.set_text_color(*_COR_TEXTO)
                    _pdf.cell(0, 8, f"Período: {_r_ini.strftime('%d/%m/%Y')} a {_r_fim.strftime('%d/%m/%Y')}", ln=True)
                    _pdf.ln(8)
                    
                    # Dados
                    _pdf.set_font("Helvetica", "", 11)
                    _pdf.cell(0, 8, f"Atendimentos no período: {_n_at}", ln=True)
                    _pdf.cell(0, 8, f"Total de clientes: {_n_cli}", ln=True)
                    _pdf.cell(0, 8, f"Vendas no período: {_n_vendas}", ln=True)
                    _pdf.cell(0, 8, f"Receita no período: R$ {_val_vendas:,.2f}", ln=True)
                    
                    _pdf_bytes = bytes(_pdf.output())
                    import base64 as _b64r
                    _b64_rel = _b64r.b64encode(_pdf_bytes).decode()
                    _col_r1, _col_r2 = st.columns(2)
                    with _col_r1:
                        st.download_button("⬇️ Baixar PDF", data=_pdf_bytes,
                                           file_name=f"relatorio_{_r_ini}_{_r_fim}.pdf",
                                           mime="application/pdf", key="dl_pdf_rel")
                    with _col_r2:
                        st.markdown(f'<a href="data:application/pdf;base64,{_b64_rel}" target="_blank" style="display:inline-block;width:100%;text-align:center;padding:0.5rem 1rem;background:#d59c9c;color:white;border-radius:8px;text-decoration:none;font-weight:600;">📤 Abrir / Compartilhar</a>', unsafe_allow_html=True)
                except Exception as _e:
                    st.error(f"Erro ao gerar PDF: {_e}")

        # ══════════════════════════════════════════
        # ABA 2 — VENDAS
        # ══════════════════════════════════════════
        with aba_vendas:
            col_vd, col_vf, col_vp = st.columns([1, 1, 1])
            with col_vd:
                _v_ini = st.date_input("De", value=_ini_mes, key="rel_v_ini", format="DD/MM/YYYY")
            with col_vf:
                _v_fim = st.date_input("Até", value=_data_hoje, key="rel_v_fim", format="DD/MM/YYYY")
            with col_vp:
                _v_pag = st.selectbox("Forma de pagamento", ["Todas", "pix", "credito", "debito", "dinheiro"], key="rel_v_pag")

            try:
                from models.sale import Sale, SaleItem
                _qv = db.query(Sale, Client).join(Client, Sale.cliente_id == Client.id, isouter=True).filter(
                    Sale.data_venda >= str(_v_ini), Sale.data_venda <= str(_v_fim))
                if _v_pag != "Todas":
                    _qv = _qv.filter(Sale.forma_pagamento == _v_pag)
                _rv = _qv.all()

                _rows_v = []
                for _s, _c in _rv:
                    _itens = db.query(SaleItem).filter(SaleItem.sale_id == _s.id).all()
                    for _it in _itens:
                        _rows_v.append({
                            "Data": str(_s.data_venda)[:10],
                            "Cliente": _c.nome if _c else "—",
                            "Procedimento": _it.procedimento or "—",
                            "Tipo": _it.tipo or "—",
                            "Sessões (total)": _it.sessoes_total or "—",
                            "Sessões (usadas)": _it.sessoes_usadas or 0,
                            "Valor (R$)": f"{float(_it.valor or 0):,.2f}",
                            "Pagamento": _s.forma_pagamento or "—",
                            "Obs": _s.observacoes or "",
                        })

                if _rows_v:
                    _df_v2 = pd.DataFrame(_rows_v)
                    st.dataframe(_df_v2, use_container_width=True, hide_index=True)
                    _total_v = sum(float(r.get("Valor (R$)", "0").replace(",", "")) for r in _rows_v)
                    st.markdown(f"**Total de itens:** {len(_rows_v)} | **Valor total: R$ {_total_v:,.2f}**")
                    st.download_button("📥 Exportar CSV", data=_df_v2.to_csv(index=False).encode("utf-8"),
                                       file_name=f"vendas_{_v_ini}_{_v_fim}.csv", mime="text/csv", key="dl_csv_v")
                else:
                    st.info("Nenhuma venda no período/filtro selecionado.")
            except Exception as _e:
                st.warning(f"Erro ao carregar vendas: {_e}")

        # ══════════════════════════════════════════
        # ABA 3 — ESTOQUE
        # ══════════════════════════════════════════
        with aba_estoque:
            try:
                from models.stock import Product, StockLote, StockMovement
                st.markdown("#### Produtos e lotes ativos")
                _prods = db.query(Product).order_by(Product.nome.asc()).all()
                _rows_e = []
                for _p in _prods:
                    _lotes = db.query(StockLote).filter(StockLote.produto_id == _p.id).all()
                    _qtd_total = sum(float(_l.quantidade_atual or 0) for _l in _lotes)
                    _lotes_str = ", ".join([f"Lote {_l.lote or 'S/N'}: {_l.quantidade_atual}" for _l in _lotes]) or "—"
                    _alerta = "⚠️ Baixo" if any(
                        float(_l.quantidade_atual or 0) <= 5 for _l in _lotes
                    ) else "OK"
                    _rows_e.append({
                        "Produto": _p.nome,
                        "Categoria": _p.categoria or "—",
                        "Qtd total": _qtd_total,
                        "Lotes": _lotes_str,
                        "Alerta": _alerta,
                    })
                if _rows_e:
                    _df_e = pd.DataFrame(_rows_e)
                    st.dataframe(_df_e, use_container_width=True, hide_index=True)
                    st.download_button("📥 Exportar CSV produtos", data=_df_e.to_csv(index=False).encode("utf-8"),
                                       file_name="estoque_produtos.csv", mime="text/csv", key="dl_est_prod")
                else:
                    st.info("Nenhum produto cadastrado.")

                st.markdown("#### Movimentações")
                _movs = db.query(StockMovement).order_by(StockMovement.data.desc()).limit(500).all()
                if _movs:
                    _rows_m = [{
                        "Data": str(_m.data)[:10],
                        "Produto": next((p.nome for p in _prods if any(l.id == _m.lote_id for l in db.query(StockLote).filter(StockLote.produto_id == p.id).all())), "—"),
                        "Lote": next((l.lote for l in db.query(StockLote).filter(StockLote.id == _m.lote_id).all()), "—"),
                        "Tipo": _m.tipo or "—",
                        "Quantidade": _m.quantidade,
                        "Motivo": _m.motivo or "—",
                    } for _m in _movs]
                    _df_m = pd.DataFrame(_rows_m)
                    st.dataframe(_df_m, use_container_width=True, hide_index=True)
                    st.download_button("📥 Exportar CSV movimentações", data=_df_m.to_csv(index=False).encode("utf-8"),
                                       file_name="movimentacoes_estoque.csv", mime="text/csv", key="dl_est_mov")
                else:
                    st.info("Nenhuma movimentação registrada.")
            except Exception as _e:
                st.warning(f"Erro ao carregar estoque: {_e}")

        # ══════════════════════════════════════════
        # ABA 4 — CLIENTES
        # ══════════════════════════════════════════
        with aba_clientes:
            _n_cli_total = db.query(Client).count()
            st.metric("Total de clientes cadastrados", _n_cli_total)
            st.info("A tabela completa de clientes não é exibida aqui para preservar a privacidade. Use o botão abaixo para exportar.")
            if st.button("📥 Exportar lista de clientes (CSV)", use_container_width=True, key="dl_cli_csv"):
                _df_cli = pd.read_sql(db.query(Client).order_by(Client.nome.asc()).statement, db.bind)
                _colunas_exp = [c for c in ["nome", "cpf", "telefone", "email", "data_nascimento",
                                             "profissao", "endereco", "bairro", "cidade", "peso",
                                             "altura", "imc", "neoplasia", "epilepsia"] if c in _df_cli.columns]
                st.download_button("⬇️ Baixar CSV", data=_df_cli[_colunas_exp].to_csv(index=False).encode("utf-8"),
                                   file_name="clientes.csv", mime="text/csv", key="dl_cli_csv2")
    finally:
        db.close()


# ====== TELA: CONTRATOS ======
def tela_contratos():
    header_titulo("Módulo de Contratos", "Geração e PDF")
    db = SessionLocal()
    try:
        clientes = db.query(Client).order_by(Client.nome.asc()).all()
        mapa_cli = {f"{c.nome} ({c.cpf})": c for c in clientes}

        col1, col2 = st.columns(2)
        with col1:
            cliente_sel = st.selectbox("Cliente", list(mapa_cli.keys()) if mapa_cli else ["—"])
            cpf_exibir = mapa_cli[cliente_sel].cpf if cliente_sel and cliente_sel in mapa_cli else ""
            st.text_input("CPF do cliente", value=cpf_exibir, disabled=True)
            tipo_trat = st.text_input("Tipo de tratamento*")
            valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01)
        with col2:
            forma = st.text_input("Forma de pagamento")
            parc = st.text_input("Parcelamento (ex.: 3x)")
            assinatura = st.text_input("Assinatura digital")

        if st.button("Gerar contrato"):
            if not cliente_sel or cliente_sel == "—" or not tipo_trat or valor <= 0:
                st.error("Preencha os campos obrigatórios.")
            else:
                cli_obj = mapa_cli[cliente_sel]
                c = Contract(
                    cliente_id=cli_obj.id,
                    tipo_tratamento=tipo_trat,
                    valor=valor,
                    forma_pagamento=forma,
                    parcelamento=parc,
                    assinatura_digital=assinatura,
                )
                db.add(c)
                db.commit()
                path = gerar_pdf_contrato(c.id, destino=f"contrato_{c.id}.pdf")
                with open(path, "rb") as f:
                    _contrato_bytes = f.read()
                import base64 as _b64c
                _b64_contrato = _b64c.b64encode(_contrato_bytes).decode()
                _col_c1, _col_c2 = st.columns(2)
                with _col_c1:
                    st.download_button("⬇️ Baixar PDF", data=_contrato_bytes, file_name=f"contrato_{c.id}.pdf")
                with _col_c2:
                    st.markdown(f'<a href="data:application/pdf;base64,{_b64_contrato}" target="_blank" style="display:inline-block;width:100%;text-align:center;padding:0.5rem 1rem;background:#d59c9c;color:white;border-radius:8px;text-decoration:none;font-weight:600;">📤 Abrir / Compartilhar</a>', unsafe_allow_html=True)
                st.success("Contrato gerado.")
    finally:
        db.close()


# ====== TELA: FICHA DO CLIENTE ======
def tela_ficha_cliente():
    header_titulo("Ficha do Cliente", "Busca, ficha completa e histórico")
    inicializar_state_cliente()

    db = SessionLocal()
    try:
        render_sugestoes_cliente(db, "", "ficha")

        cliente_id = st.session_state.get("ficha_cliente_id", 0)
        if not cliente_id:
            st.info("Digite o nome da cliente para ver sugestões e selecionar uma ficha.")
            return

        cli = db.get(Client, cliente_id)
        if not cli:
            st.error("Cliente não encontrado.")
            return

        st.markdown(f"## {cli.nome}")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.write(f"**CPF:** {cli.cpf or ''}")
            st.write(f"**Data de nascimento:** {formatar_data_br(cli.data_nascimento)}")
            st.write(f"**Telefone:** {cli.telefone or ''}")
            st.write(f"**E-mail:** {cli.email or ''}")
        with c2:
            st.write(f"**Profissão:** {cli.profissao or ''}")
            st.write(f"**Endereço:** {cli.endereco or ''}")
            st.write(f"**Bairro:** {cli.bairro or ''}")
            st.write(f"**Cidade:** {cli.cidade or ''}")
        with c3:
            st.write(f"**Peso:** {cli.peso or ''}")
            st.write(f"**Altura:** {cli.altura or ''}")
            st.write(f"**IMC:** {cli.imc or ''}")
            st.write(f"**Termo aceito:** {'Sim' if cli.termo_aceite else 'Não'}")

        st.markdown("---")
        st.markdown("### Informações clínicas")
        st.write(f"**Queixa principal:** {cli.queixa_principal or ''}")
        st.write(f"**Neoplasia:** {'Sim' if cli.neoplasia else 'Não'}")
        st.write(f"**Epilepsia:** {'Sim' if cli.epilepsia else 'Não'}")
        st.write(f"**Funcionamento intestinal:** {cli.funcionamento_intestinal or ''}")
        st.write(f"**Uso de vitaminas:** {cli.uso_vitaminas or ''}")
        st.write(f"**Exames recentes:** {cli.exames_recentes or ''}")

        st.markdown("### Histórico / outras condições")
        st.text_area(
            "Dados complementares",
            value=cli.outras_condicoes or "",
            height=250,
            disabled=True,
            key=f"ficha_outras_{cli.id}",
        )

        st.markdown("### Marcação corporal")
        st.text_area(
            "Marcação corporal",
            value=cli.marcacao_corporal or "",
            height=120,
            disabled=True,
            key=f"ficha_marc_{cli.id}",
        )

        st.markdown("---")
        abas = st.tabs(["Atendimentos", "Biometria", "Pré-avaliações"])

        with abas[0]:
            atend = pd.read_sql(
                db.query(Appointment)
                .filter(Appointment.cliente_id == cli.id)
                .order_by(Appointment.data.desc(), Appointment.id.desc())
                .statement,
                db.bind,
            )
            if not atend.empty:
                if "data" in atend.columns:
                    atend["data"] = pd.to_datetime(atend["data"], errors="coerce").dt.strftime("%d/%m/%Y")
                st.dataframe(atend, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum atendimento encontrado.")

        with abas[1]:
            bio = pd.read_sql(
                db.query(Biometrics)
                .filter(Biometrics.cliente_id == cli.id)
                .order_by(Biometrics.data_medicao.desc())
                .statement,
                db.bind,
            )
            if not bio.empty:
                if "data_medicao" in bio.columns:
                    bio["data_medicao"] = pd.to_datetime(bio["data_medicao"], errors="coerce").dt.strftime("%d/%m/%Y")
                st.dataframe(bio, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma biometria cadastrada.")

        with abas[2]:
            aval = pd.read_sql(
                db.query(Assessment)
                .filter(Assessment.cliente_id == cli.id)
                .order_by(Assessment.criado_em.desc())
                .statement,
                db.bind,
            )
            if not aval.empty:
                if "criado_em" in aval.columns:
                    aval["criado_em"] = pd.to_datetime(aval["criado_em"], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")
                st.dataframe(aval, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma pré-avaliação encontrada.")
    finally:
        db.close()


# ====== TELA: VENDAS ======
def tela_vendas():
    header_titulo("Vendas", "Registro de vendas unitárias e pacotes")

    db = SessionLocal()
    try:
        # ── Inicializa itens da venda na sessão ──
        if "venda_itens" not in st.session_state:
            st.session_state["venda_itens"] = []

        st.markdown("### Nova Venda")

        # Busca de cliente
        def buscar_cli_venda(termo):
            if not termo or len(termo) < 2:
                return []
            like = f"%{termo}%"
            res = db.query(Client).filter(
                (Client.nome.like(like)) | (Client.cpf.like(like)) | (Client.telefone.like(like))
            ).order_by(Client.nome).limit(20).all()
            return [f"{c.nome} | {c.cpf or c.telefone or ''}" for c in res]

        sel_cli = st_searchbox(buscar_cli_venda, label="Cliente*", key="venda_cliente_search", placeholder="Digite o nome")

        # Resolve ID do cliente selecionado
        venda_cliente_id = st.session_state.get("venda_cliente_id_selecionado", 0)
        if sel_cli:
            nome_base = str(sel_cli).split("|")[0].strip()
            c_match = db.query(Client).filter(Client.nome.like(f"%{nome_base}%")).first()
            if c_match and c_match.id != venda_cliente_id:
                st.session_state["venda_cliente_id_selecionado"] = c_match.id
                venda_cliente_id = c_match.id

        col_v1, col_v2 = st.columns(2)
        with col_v1:
            data_venda = st.date_input("Data da venda", value=_hoje(), key="venda_data", format="DD/MM/YYYY")
        with col_v2:
            pagamento = st.selectbox("Forma de pagamento*", ["Cartão de Crédito", "Cartão de Débito", "Pix"], key="venda_pag")

        obs_venda = st.text_input("Observações (opcional)", key="venda_obs")

        st.markdown("#### Itens da venda")

        # ── Adicionar item ──
        with st.expander("➕ Adicionar item", expanded=True):
            # Buscar procedimentos cadastrados para auto-preencher
            _procs_cadastrados = db.query(Tratamento).filter(Tratamento.ativo == True).order_by(Tratamento.nome).all()
            _nomes_procs = ["— digitar manualmente —"] + [p.nome for p in _procs_cadastrados]
            _mapa_procs = {p.nome: p for p in _procs_cadastrados}

            col_i0, col_i1 = st.columns([2, 2])
            with col_i0:
                proc_selecionado = st.selectbox("Procedimento cadastrado", _nomes_procs, key="item_proc_sel")
            with col_i1:
                tipo_item = st.selectbox("Tipo", ["Unitário", "Pacote"], key="item_tipo")

            # Auto-preencher valor se selecionou procedimento cadastrado
            _val_default = 0.0
            _sessoes_default = 2
            if proc_selecionado != "— digitar manualmente —" and proc_selecionado in _mapa_procs:
                _p_ref = _mapa_procs[proc_selecionado]
                if tipo_item == "Pacote" and _p_ref.valor_pacote:
                    _val_default = _p_ref.valor_pacote
                    _sessoes_default = _p_ref.sessoes_pacote or 10
                elif _p_ref.valor_unitario:
                    _val_default = _p_ref.valor_unitario

            col_i2, col_i3 = st.columns([3, 1])
            with col_i2:
                if proc_selecionado == "— digitar manualmente —":
                    proc_item = st.text_input("Procedimento*", key="item_proc")
                else:
                    proc_item = proc_selecionado
                    st.text_input("Procedimento*", value=proc_selecionado, disabled=True, key="item_proc_show")
            with col_i3:
                valor_item = st.number_input("Valor (R$)*", min_value=0.0, step=0.01, value=_val_default, key="item_valor")

            sessoes_item = 1
            if tipo_item == "Pacote":
                sessoes_item = st.number_input("Nº de sessões*", min_value=2, step=1, value=_sessoes_default, key="item_sessoes")

            if st.button("Adicionar item", use_container_width=True):
                if not proc_item.strip():
                    st.error("Informe o procedimento.")
                elif valor_item <= 0:
                    st.error("Informe um valor maior que zero.")
                else:
                    st.session_state["venda_itens"].append({
                        "procedimento": proc_item.strip(),
                        "tipo": tipo_item.lower(),
                        "sessoes_total": int(sessoes_item),
                        "valor": valor_item,
                    })
                    st.rerun()

        # ── Lista de itens adicionados ──
        itens = st.session_state["venda_itens"]
        if itens:
            st.markdown("**Itens adicionados:**")
            for i, it in enumerate(itens):
                col_it, col_rm = st.columns([5, 1])
                with col_it:
                    tipo_label = "📦 Pacote" if it["tipo"] == "pacote" else "1️⃣ Unitário"
                    sessoes_label = f" — {it['sessoes_total']} sessões" if it["tipo"] == "pacote" else ""
                    st.write(f"**{it['procedimento']}** {tipo_label}{sessoes_label} — R$ {it['valor']:.2f}")
                with col_rm:
                    if st.button("✕", key=f"rm_item_{i}"):
                        st.session_state["venda_itens"].pop(i)
                        st.rerun()

            total = sum(it["valor"] for it in itens)
            st.markdown(f"**Total: R$ {total:.2f}**")

            if st.button("💾 Salvar Venda", use_container_width=True, type="primary"):
                if not venda_cliente_id:
                    st.error("Selecione a cliente.")
                else:
                    nova_venda = Sale(
                        cliente_id=venda_cliente_id,
                        data_venda=data_venda,
                        forma_pagamento=pagamento,
                        valor_total=total,
                        observacoes=obs_venda or None,
                    )
                    db.add(nova_venda)
                    db.flush()
                    for it in itens:
                        db.add(SaleItem(
                            sale_id=nova_venda.id,
                            procedimento=it["procedimento"],
                            tipo=it["tipo"],
                            sessoes_total=it["sessoes_total"],
                            sessoes_usadas=0,
                            valor=it["valor"],
                        ))
                    db.commit()
                    st.success("Venda registrada com sucesso!")
                    st.session_state["venda_itens"] = []
                    st.session_state["venda_cliente_id_selecionado"] = 0
                    st.rerun()
        else:
            st.info("Nenhum item adicionado ainda.")

        # ── Vendas recentes ──
        st.markdown("---")
        st.markdown("### Vendas recentes")

        col_filtro_v, _ = st.columns([1, 3])
        with col_filtro_v:
            filtro_tipo_venda = st.selectbox("Filtrar por tipo", ["Todos", "Pacote", "Unitário"], key="venda_filtro_tipo")

        vendas_rec = db.query(Sale).order_by(Sale.data_venda.desc(), Sale.id.desc()).limit(50).all()
        if vendas_rec:
            for v in vendas_rec:
                # Determinar tipo predominante da venda
                tipos_itens = set(it.tipo for it in v.itens)
                if "pacote" in tipos_itens and "unitario" in tipos_itens:
                    tipo_venda = "Misto"
                elif "pacote" in tipos_itens:
                    tipo_venda = "Pacote"
                else:
                    tipo_venda = "Unitário"

                # Aplicar filtro
                if filtro_tipo_venda == "Pacote" and "pacote" not in tipos_itens:
                    continue
                if filtro_tipo_venda == "Unitário" and "unitario" not in tipos_itens:
                    continue

                procs = ", ".join(f"{it.procedimento}" for it in v.itens)
                col_info_v, col_menu_v = st.columns([6, 0.4])
                with col_info_v:
                    st.write(
                        f"**{v.data_venda.strftime('%d/%m/%Y')}** — "
                        f"{v.cliente.nome if v.cliente else '—'} | "
                        f"{tipo_venda} | {procs} | "
                        f"R$ {v.valor_total:.2f} | {v.forma_pagamento}"
                    )
                with col_menu_v:
                    with st.popover("⋮", use_container_width=True):
                        if st.button("✏️ Editar", key=f"venda_edit_{v.id}"):
                            st.session_state["venda_editando"] = v.id
                            st.rerun()
                        if st.button("🗑️ Excluir", key=f"venda_del_{v.id}"):
                            db.delete(v)
                            db.commit()
                            st.rerun()
        else:
            st.info("Nenhuma venda registrada.")

        # ── Formulário de edição de venda ──
        if st.session_state.get("venda_editando"):
            _vid = st.session_state["venda_editando"]
            _venda_ed = db.get(Sale, _vid)
            if _venda_ed:
                st.markdown("---")
                st.markdown("#### Editar Venda")
                with st.form("form_editar_venda", clear_on_submit=False):
                    _ed_data_v = st.date_input("Data", value=_venda_ed.data_venda, format="DD/MM/YYYY", key="ed_venda_data")
                    _ed_pag_v = st.selectbox(
                        "Forma de pagamento",
                        ["Cartão de Crédito", "Cartão de Débito", "Pix"],
                        index=["Cartão de Crédito", "Cartão de Débito", "Pix"].index(_venda_ed.forma_pagamento)
                        if _venda_ed.forma_pagamento in ["Cartão de Crédito", "Cartão de Débito", "Pix"] else 0,
                        key="ed_venda_pag",
                    )
                    _ed_obs_v = st.text_input("Observações", value=_venda_ed.observacoes or "", key="ed_venda_obs")
                    col_sv2, col_cn2 = st.columns(2)
                    with col_sv2:
                        _salvar_venda_ed = st.form_submit_button("💾 Salvar", use_container_width=True)
                    with col_cn2:
                        _cancelar_venda_ed = st.form_submit_button("Cancelar", use_container_width=True)
                if _salvar_venda_ed:
                    _venda_ed.data_venda = _ed_data_v
                    _venda_ed.forma_pagamento = _ed_pag_v
                    _venda_ed.observacoes = _ed_obs_v or None
                    db.commit()
                    st.success("Venda atualizada!")
                    st.session_state.pop("venda_editando", None)
                    st.rerun()
                if _cancelar_venda_ed:
                    st.session_state.pop("venda_editando", None)
                    st.rerun()
    finally:
        db.close()


# ====== TELA: USUÁRIOS ======
def _modal_editar_usuario(uid: int):
    @st.dialog("Editar Usuário", width="large")
    def _abrir():
        db = SessionLocal()
        try:
            u = db.get(User, uid)
            if not u:
                st.error("Usuário não encontrado.")
                return
            nome_e = st.text_input("Nome", value=u.nome, key=f"dlg_ed_nome_{uid}")
            email_e = st.text_input("E-mail", value=u.email, key=f"dlg_ed_email_{uid}")
            perfil_e = st.selectbox(
                "Perfil", ["admin", "recepcao", "profissional"],
                index=["admin", "recepcao", "profissional"].index(u.perfil)
                if u.perfil in ["admin", "recepcao", "profissional"] else 0,
                key=f"dlg_ed_perfil_{uid}",
            )
            ativo_e = st.checkbox("Ativo", value=bool(u.ativo), key=f"dlg_ed_ativo_{uid}")
            nova_senha_e = st.text_input(
                "Nova senha (deixe vazio para manter)", type="password", key=f"dlg_ed_senha_{uid}"
            )
            col_s, col_c = st.columns(2)
            with col_s:
                if st.button("💾 Salvar alterações", use_container_width=True, key=f"dlg_ed_salvar_{uid}"):
                    u.nome = nome_e
                    u.email = email_e
                    u.perfil = perfil_e
                    u.ativo = ativo_e
                    if nova_senha_e:
                        u.senha_hash = hash_password(nova_senha_e)
                    db.commit()
                    st.success("Usuário atualizado.")
                    st.rerun()
            with col_c:
                if st.button("Cancelar", use_container_width=True, key=f"dlg_ed_cancel_{uid}"):
                    st.rerun()
        finally:
            db.close()
    _abrir()


def _modal_excluir_usuario(uid: int, nome_usuario: str):
    @st.dialog(f"Excluir usuário", width="small")
    def _abrir():
        st.warning(f"Tem certeza que deseja excluir o usuário **{nome_usuario}**? Esta ação é irreversível.")
        col_c, col_d = st.columns(2)
        with col_c:
            if st.button("Cancelar", use_container_width=True, key=f"dlg_del_cancel_{uid}"):
                st.rerun()
        with col_d:
            if st.button("🗑️ Confirmar exclusão", use_container_width=True,
                          key=f"dlg_del_confirm_{uid}", type="primary"):
                db = SessionLocal()
                try:
                    u = db.get(User, uid)
                    if u:
                        db.delete(u)
                        db.commit()
                finally:
                    db.close()
                st.success(f"Usuário {nome_usuario} excluído.")
                st.rerun()
    _abrir()


# ====== TELA: CADASTROS (Materiais e Tratamentos) ======
def tela_cadastros():
    header_titulo("Cadastros", "Materiais e procedimentos")
    db = SessionLocal()
    try:
        aba_prod, aba_trat = st.tabs(["Produtos", "Procedimentos"])

        # ────── ABA PRODUTOS ──────
        with aba_prod:
            db_prod = SessionLocal()
            try:
                st.markdown("### Produtos cadastrados")
                produtos_lista = db_prod.query(Product).order_by(Product.nome.asc()).all()
                if produtos_lista:
                    import pandas as pd
                    rows_prod = []
                    ids_prod = []
                    for p in produtos_lista:
                        ids_prod.append(p.id)
                        rows_prod.append({
                            "Selecionar": False,
                            "ID": p.id,
                            "Nome": p.nome,
                            "Categoria": p.categoria or "—",
                        })
                    df_prod = pd.DataFrame(rows_prod)
                    edited_df_prod = st.data_editor(
                        df_prod,
                        hide_index=True,
                        column_config={"Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False)},
                        disabled=["ID", "Nome", "Categoria"],
                        key="prod_editor"
                    )
                    
                    # Identificar selecionado
                    linha_sel_prod = None
                    for i, row in edited_df_prod.iterrows():
                        if row.get("Selecionar"):
                            linha_sel_prod = ids_prod[i]
                            break
                    
                    # Botões
                    col_p1, col_p2, col_p3 = st.columns([1, 1, 4])
                    with col_p1:
                        btn_edit_prod = st.button("✏️ Editar", key="btn_edit_prod", disabled=(linha_sel_prod is None))
                    with col_p2:
                        btn_del_prod = st.button("🗑️ Excluir", key="btn_del_prod", disabled=(linha_sel_prod is None))
                    
                    if btn_del_prod and linha_sel_prod:
                        p_del = db_prod.get(Product, linha_sel_prod)
                        if p_del:
                            db_prod.delete(p_del)
                            db_prod.commit()
                            st.success("Produto excluído!")
                            st.rerun()
                    
                    if btn_edit_prod and linha_sel_prod:
                        st.session_state["prod_editando"] = linha_sel_prod
                        st.rerun()
                    
                    if st.session_state.get("prod_editando"):
                        p_ed = db_prod.get(Product, st.session_state["prod_editando"])
                        if p_ed:
                            st.markdown("---")
                            st.markdown("#### ✏️ Editar produto")
                            new_nome_p = st.text_input("Nome", value=p_ed.nome, key="prod_ed_nome")
                            new_cat_p = st.selectbox("Categoria", ["descartavel", "injetavel", "outro"], 
                                index=["descartavel", "injetavel", "outro"].index(p_ed.categoria) if p_ed.categoria in ["descartavel", "injetavel", "outro"] else 2,
                                key="prod_ed_cat")
                            bp1, bp2 = st.columns(2)
                            with bp1:
                                if st.button("💾 Salvar", key="prod_save", use_container_width=True):
                                    p_ed.nome = new_nome_p
                                    p_ed.categoria = new_cat_p
                                    db_prod.commit()
                                    del st.session_state["prod_editando"]
                                    st.success("Produto atualizado!")
                                    st.rerun()
                            with bp2:
                                if st.button("❌ Cancelar", key="prod_cancel", use_container_width=True):
                                    del st.session_state["prod_editando"]
                                    st.rerun()
                else:
                    st.info("Nenhum produto cadastrado ainda.")

                st.markdown("---")
                st.markdown("### Cadastrar novo produto")
                with st.form("form_novo_produto", clear_on_submit=True):
                    nome_prod = st.text_input("Nome do produto*")
                    cat_prod = st.selectbox("Categoria*", ["descartavel", "injetavel", "outro"])
                    salvar_prod = st.form_submit_button("Salvar produto", use_container_width=True)

                if salvar_prod:
                    if not nome_prod.strip():
                        st.error("Nome é obrigatório.")
                    else:
                        existe_prod = db_prod.query(Product).filter(Product.nome == nome_prod.strip()).first()
                        if existe_prod:
                            st.warning("Produto com este nome já cadastrado.")
                        else:
                            db_prod.add(Product(nome=nome_prod.strip(), categoria=cat_prod))
                            db_prod.commit()
                            st.success("Produto cadastrado!")
                            st.rerun()
            finally:
                db_prod.close()

# ────── ABA PROCEDIMENTOS ──────
        with aba_trat:
            st.markdown("### Novo Procedimento")
            col1, col2 = st.columns(2)
            with col1:
                nome_trat = st.text_input("Nome do procedimento*", key="trat_nome")
                desc_trat = st.text_input("Descrição (opcional)", key="trat_desc")
            with col2:
                valor_unit = st.number_input("Valor unitário (R$)", min_value=0.0, step=0.01, key="trat_val_unit")
                valor_pac = st.number_input("Valor pacote (R$)", min_value=0.0, step=0.01, key="trat_val_pac")
                sessoes_pac = st.number_input("Sessões do pacote", min_value=0, step=1, value=0, key="trat_sessoes")

            if st.button("Salvar procedimento", key="trat_salvar", use_container_width=True):
                if not nome_trat.strip():
                    st.error("Informe o nome do procedimento.")
                else:
                    existe = db.query(Tratamento).filter(
                        Tratamento.nome == nome_trat.strip(),
                        Tratamento.ativo == True
                    ).first()
                    if existe:
                        st.warning("Já existe um procedimento com este nome.")
                    else:
                        db.add(Tratamento(
                            nome=nome_trat.strip(),
                            descricao=desc_trat.strip() or None,
                            valor_unitario=valor_unit if valor_unit > 0 else None,
                            valor_pacote=valor_pac if valor_pac > 0 else None,
                            sessoes_pacote=sessoes_pac if sessoes_pac > 0 else None,
                        ))
                        db.commit()
                        st.success("Procedimento cadastrado!")
                        st.rerun()

            st.markdown("---")
            st.markdown("### Procedimentos Cadastrados")
            tratamentos = db.query(Tratamento).filter(Tratamento.ativo == True).order_by(Tratamento.nome.asc()).all()
            if tratamentos:
                import pandas as pd
                rows_proc = []
                ids_trat = []
                for trat in tratamentos:
                    ids_trat.append(trat.id)
                    rows_proc.append({
                        "Selecionar": False,
                        "Nome": trat.nome,
                        "Descrição": trat.descricao or "—",
                        "Valor Unit. (R$)": f"{trat.valor_unitario:.2f}" if trat.valor_unitario else "—",
                        "Valor Pacote (R$)": f"{trat.valor_pacote:.2f}" if trat.valor_pacote else "—",
                        "Sessões Pacote": trat.sessoes_pacote or "—",
                    })
                
                df_proc = pd.DataFrame(rows_proc)
                edited_df_proc = st.data_editor(
                    df_proc,
                    hide_index=True,
                    column_config={"Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False)},
                    disabled=["Nome", "Descrição", "Valor Unit. (R$)", "Valor Pacote (R$)", "Sessões Pacote"],
                    key="proc_editor"
                )
                
                # Identificar linha selecionada
                linha_sel_proc = None
                for i, row in edited_df_proc.iterrows():
                    if row.get("Selecionar"):
                        linha_sel_proc = ids_trat[i]
                        break
                
                # Botões de ação
                col_proc1, col_proc2, col_proc3 = st.columns([1, 1, 4])
                with col_proc1:
                    btn_editar_proc = st.button("✏️ Editar", key="btn_editar_proc", disabled=(linha_sel_proc is None))
                with col_proc2:
                    btn_excluir_proc = st.button("🗑️ Excluir", key="btn_excluir_proc", disabled=(linha_sel_proc is None))
                
                if btn_excluir_proc and linha_sel_proc:
                    trat_del = db.get(Tratamento, linha_sel_proc)
                    if trat_del:
                        trat_del.ativo = False
                        db.commit()
                        st.success("Procedimento excluído!")
                        st.rerun()
                
                if btn_editar_proc and linha_sel_proc:
                    st.session_state["proc_editando"] = linha_sel_proc
                    st.rerun()
                
                # Form de edição
                if st.session_state.get("proc_editando"):
                    trat_ed = db.get(Tratamento, st.session_state["proc_editando"])
                    if trat_ed:
                        st.markdown("---")
                        st.markdown("#### ✏️ Editar procedimento")
                        pec1, pec2 = st.columns(2)
                        with pec1:
                            new_nome_proc = st.text_input("Nome", value=trat_ed.nome, key="proc_ed_nome")
                            new_desc_proc = st.text_area("Descrição", value=trat_ed.descricao or "", key="proc_ed_desc")
                            new_val_unit = st.number_input("Valor Unitário (R$)", value=float(trat_ed.valor_unitario or 0), min_value=0.0, step=0.01, key="proc_ed_vunit")
                        with pec2:
                            new_val_pac = st.number_input("Valor Pacote (R$)", value=float(trat_ed.valor_pacote or 0), min_value=0.0, step=0.01, key="proc_ed_vpac")
                            new_sess_pac = st.number_input("Sessões Pacote", value=int(trat_ed.sessoes_pacote or 0), min_value=0, step=1, key="proc_ed_sess")
                        
                        bpc1, bpc2 = st.columns(2)
                        with bpc1:
                            if st.button("💾 Salvar", key="proc_save", use_container_width=True):
                                trat_ed.nome = new_nome_proc
                                trat_ed.descricao = new_desc_proc if new_desc_proc else None
                                trat_ed.valor_unitario = new_val_unit if new_val_unit > 0 else None
                                trat_ed.valor_pacote = new_val_pac if new_val_pac > 0 else None
                                trat_ed.sessoes_pacote = new_sess_pac if new_sess_pac > 0 else None
                                db.commit()
                                del st.session_state["proc_editando"]
                                st.success("Procedimento atualizado!")
                                st.rerun()
                        with bpc2:
                            if st.button("❌ Cancelar", key="proc_cancel", use_container_width=True):
                                del st.session_state["proc_editando"]
                                st.rerun()
            else:
                st.info("Nenhum procedimento cadastrado ainda.")
    finally:
        db.close()


def tela_usuarios():
    header_titulo("Usuários", "Perfis e acesso ao sistema")
    perfil_atual = st.session_state.user.get("perfil", "")
    user_id_atual = st.session_state.user.get("id")
    is_admin = perfil_atual == "admin"

    db = SessionLocal()
    try:
        # ── Tabela com seleção (somente admin) ─────────────────────────────
        if is_admin:
            st.markdown("### Usuários cadastrados")
            todos = db.query(User).order_by(User.id.asc()).all()

            # Linha de checkbox por usuário
            _sel_id = st.session_state.get("usr_selecionado_id")
            for u in todos:
                col_chk, col_info, col_ed, col_del = st.columns([0.3, 4, 1, 1])
                with col_chk:
                    marcado = st.checkbox(
                        "", key=f"usr_chk_{u.id}",
                        value=(_sel_id == u.id),
                        label_visibility="collapsed",
                    )
                    if marcado and _sel_id != u.id:
                        st.session_state["usr_selecionado_id"] = u.id
                        st.rerun()
                    elif not marcado and _sel_id == u.id:
                        st.session_state["usr_selecionado_id"] = None
                        st.rerun()
                with col_info:
                    ativo_tag = "🟢" if u.ativo else "🔴"
                    st.markdown(
                        f"{ativo_tag} **{u.nome}** &nbsp;·&nbsp; {u.email} &nbsp;·&nbsp; "
                        f"<span style='font-size:0.8rem;color:#9b7e69'>{u.perfil}</span>",
                        unsafe_allow_html=True,
                    )
                with col_ed:
                    if u.id == _sel_id:
                        if st.button("✏️ Editar", key=f"usr_btn_ed_{u.id}", use_container_width=True):
                            _modal_editar_usuario(u.id)
                with col_del:
                    if u.id == _sel_id and u.id != user_id_atual:
                        if st.button("🗑️ Excluir", key=f"usr_btn_del_{u.id}", use_container_width=True):
                            _modal_excluir_usuario(u.id, u.nome)

            st.markdown("---")

        # ── Novo usuário (todos os perfis podem criar) ─────────────────────
        st.markdown("### Novo usuário")
        col1, col2, col3 = st.columns(3)
        with col1:
            nome_n = st.text_input("Nome", key="usr_new_nome")
            email_n = st.text_input("E-mail", key="usr_new_email")
            perfil_n = st.selectbox("Perfil", ["admin", "recepcao", "profissional"], key="usr_new_perfil")
        with col2:
            senha_n = st.text_input("Senha", type="password", key="usr_new_senha")
            ativo_n = st.checkbox("Ativo", value=True, key="usr_new_ativo")
        with col3:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            if st.button("Criar usuário", use_container_width=True, key="usr_btn_criar"):
                if not (nome_n and email_n and senha_n):
                    st.error("Preencha nome, e-mail e senha.")
                else:
                    existe = db.query(User).filter(User.email == email_n).first()
                    if existe:
                        st.error("Já existe um usuário com este e-mail.")
                    else:
                        db.add(User(nome=nome_n, email=email_n,
                                    senha_hash=hash_password(senha_n),
                                    perfil=perfil_n, ativo=ativo_n))
                        db.commit()
                        st.success("Usuário criado.")
                        st.rerun()
    finally:
        db.close()


# ====== ROTEAMENTO ======
def main():
    if not st.session_state.user:
        login_screen()
        return

    sidebar_menu()

    # ── Header global com saudação ──
    user = st.session_state.user
    hora = _agora().hour
    saudacao = "Bom dia" if hora < 12 else ("Boa tarde" if hora < 18 else "Boa noite")
    data_hoje = _agora().strftime("%d/%m/%Y")
    hora_agora = _agora().strftime("%H:%M")
    st.markdown(f"""
    <div class="gf-header">
        <div class="gf-header-left">
            <span class="gf-header-greeting">{saudacao} ✦</span>
            <span class="gf-header-name">{user['nome']}</span>
            <span class="gf-header-clinic">Gabriela Franco Saúde Integrativa</span>
        </div>
        <div class="gf-header-right">
            <span class="gf-header-date">📅 {data_hoje}</span>
            <span class="gf-header-time">🕐 {hora_agora}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    rota = st.session_state.menu

    if rota == "Dashboard":
        tela_dashboard()
    elif rota == "Agenda":
        tela_agenda()
    elif rota in ("Clientes", "Cadastro de Cliente", "Ficha do Cliente"):
        tela_clientes()
    elif rota == "Pré-avaliação":
        tela_pre_avaliacao()
    elif rota == "Atendimentos":
        tela_atendimentos()
    elif rota == "Biometria":
        tela_biometria()
    elif rota == "Vendas":
        # Verificar permissão
        perfil = st.session_state.user.get("perfil", "") if st.session_state.user else ""
        if perfil in ["admin", "recepcao"]:
            tela_vendas()
        else:
            st.error("Você não tem permissão para acessar esta página.")
            st.info("Contate o administrador do sistema.")
    elif rota == "Estoque":
        tela_estoque()
    elif rota == "Relatórios":
        # Verificar permissão - apenas admin
        perfil = st.session_state.user.get("perfil", "") if st.session_state.user else ""
        if perfil == "admin":
            tela_relatorios()
        else:
            st.error("Você não tem permissão para acessar esta página.")
            st.info("Contate o administrador do sistema.")
    elif rota == "Contratos":
        tela_contratos()
    elif rota == "Usuários":
        # Verificar permissão - apenas admin
        perfil = st.session_state.user.get("perfil", "") if st.session_state.user else ""
        if perfil == "admin":
            tela_usuarios()
        else:
            st.error("Você não tem permissão para acessar esta página.")
            st.info("Contate o administrador do sistema.")
    elif rota == "Cadastros":
        # Verificar permissão
        perfil = st.session_state.user.get("perfil", "") if st.session_state.user else ""
        if perfil in ["admin", "recepcao"]:
            tela_cadastros()
        else:
            st.error("Você não tem permissão para acessar esta página.")
            st.info("Contate o administrador do sistema.")


if __name__ == "__main__":
    main()
