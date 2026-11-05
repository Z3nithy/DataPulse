from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.jwt import verificar_token_acesso
from database import get_db

from models import User

security = HTTPBearer(auto_error=False)


def get_usuario_atual(
    credenciais: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db)
):
    if credenciais is None:
        raise HTTPException(status_code=401, detail="Autenticacao obrigatoria")
    token = credenciais.credentials

    try:
        usuario_id, token_version = verificar_token_acesso(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado"
        )

    usuario = db.query(User).filter(
        User.id == usuario_id
    ).first()

    if not usuario or not usuario.active or usuario.token_version != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado"
        )

    return usuario


def require_editor(usuario: User = Depends(get_usuario_atual)) -> User:
    if usuario.role not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Permissao de editor obrigatoria")
    return usuario


def require_admin(usuario: User = Depends(get_usuario_atual)) -> User:
    if usuario.role != "admin":
        raise HTTPException(status_code=403, detail="Permissao de administrador obrigatoria")
    return usuario