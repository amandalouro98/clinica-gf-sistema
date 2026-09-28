from models.task import Task
from models.user import User


STATUS_TAREFA = ("A fazer", "Em andamento", "Concluído")
PERFIS_GERENCIAM_TAREFAS = ("admin", "recepcao")


def pode_gerenciar_tarefas(perfil):
    return (perfil or "").strip().lower() in PERFIS_GERENCIAM_TAREFAS


def listar_tarefas(db):
    return (
        db.query(Task, User.nome)
        .outerjoin(User, Task.responsavel_id == User.id)
        .order_by(Task.criado_em.desc(), Task.id.desc())
        .all()
    )


def listar_responsaveis(db):
    return (
        db.query(User)
        .filter(User.ativo.is_(True))
        .order_by(User.nome.asc())
        .all()
    )


def _validar_tarefa(titulo, status, responsavel_id, db):
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("Informe o nome da tarefa.")
    if len(titulo) > 500:
        raise ValueError("A tarefa pode ter até 500 caracteres.")
    if status not in STATUS_TAREFA:
        raise ValueError("Selecione um status válido.")
    responsavel = db.query(User).filter_by(id=responsavel_id, ativo=True).first()
    if responsavel is None:
        raise ValueError("Selecione uma responsável ativa no sistema.")
    return titulo, responsavel


def criar_tarefa(db, perfil, titulo, status, responsavel_id):
    if not pode_gerenciar_tarefas(perfil):
        raise PermissionError("Seu perfil não pode cadastrar tarefas.")
    titulo, responsavel = _validar_tarefa(titulo, status, responsavel_id, db)
    tarefa = Task(titulo=titulo, status=status, responsavel_id=responsavel.id)
    db.add(tarefa)
    db.commit()
    db.refresh(tarefa)
    return tarefa


def atualizar_tarefa(db, perfil, tarefa_id, titulo, status, responsavel_id):
    if not pode_gerenciar_tarefas(perfil):
        raise PermissionError("Seu perfil não pode alterar tarefas.")
    tarefa = db.get(Task, tarefa_id)
    if tarefa is None:
        raise ValueError("Esta tarefa não existe mais.")
    titulo, responsavel = _validar_tarefa(titulo, status, responsavel_id, db)
    tarefa.titulo = titulo
    tarefa.status = status
    tarefa.responsavel_id = responsavel.id
    db.commit()
    return tarefa


def atualizar_status_tarefa(db, perfil, tarefa_id, status):
    if not pode_gerenciar_tarefas(perfil):
        raise PermissionError("Seu perfil não pode alterar tarefas.")
    if status not in STATUS_TAREFA:
        raise ValueError("Selecione um status válido.")
    tarefa = db.get(Task, tarefa_id)
    if tarefa is None:
        raise ValueError("Esta tarefa não existe mais.")
    tarefa.status = status
    db.commit()
    return tarefa
