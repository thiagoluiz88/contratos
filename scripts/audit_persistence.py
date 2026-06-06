from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    AIAnalysis,
    AccessProfile,
    Contract,
    ContractAdditive,
    ContractComparison,
    ContractEvent,
    ImportBatch,
    Operator,
    User,
)
from app.services.auth import PROFILE_ADMIN, hash_password


def expect(response, expected: tuple[int, ...], action: str) -> None:
    if response.status_code not in expected:
        raise RuntimeError(f"{action} falhou: HTTP {response.status_code} - {response.text[:500]}")


def main() -> None:
    marker = f"AUDIT-{uuid4().hex[:10]}"
    username = marker.lower()
    email = f"{username}@example.local"
    operator_name = f"Operadora {marker}"
    contract_ids: list[int] = []
    created_user_ids: list[int] = []
    profile_id: int | None = None

    db = SessionLocal()
    try:
        admin_profile = db.query(AccessProfile).filter(AccessProfile.name == PROFILE_ADMIN).one()
        admin_profile_id = admin_profile.id
        test_admin = User(
            username=username,
            email=email,
            password_hash=hash_password("Audit!1234"),
            full_name="Auditoria de Persistência",
            access_profile_id=admin_profile_id,
            is_active=True,
        )
        db.add(test_admin)
        db.commit()
        created_user_ids.append(test_admin.id)
    finally:
        db.close()

    try:
        with TestClient(app) as client:
            client.headers["Origin"] = "http://testserver"
            response = client.post("/login", data={"username": username, "password": "Audit!1234"})
            expect(response, (200,), "login")

            response = client.post(
                "/users/new",
                data={
                    "username": f"{username}-user",
                    "full_name": "Usuário Persistente",
                    "email": f"{username}-user@example.local",
                    "access_profile_id": admin_profile_id,
                    "password": "Audit!1234",
                    "is_active": "on",
                },
                follow_redirects=False,
            )
            expect(response, (303,), "cadastro de usuário")

            db = SessionLocal()
            try:
                created_user = db.query(User).filter(User.username == f"{username}-user").one()
                created_user_ids.append(created_user.id)
            finally:
                db.close()

            response = client.post(
                f"/users/{created_user_ids[-1]}/edit",
                data={
                    "full_name": "Usuário Persistente Editado",
                    "email": f"{username}-user-edited@example.local",
                    "access_profile_id": admin_profile_id,
                    "is_active": "on",
                },
                follow_redirects=False,
            )
            expect(response, (303,), "edição de usuário")

            response = client.post(
                f"/users/{created_user_ids[-1]}/reset-password",
                data={"password": "Audit!5678", "password_confirm": "Audit!5678"},
                follow_redirects=False,
            )
            expect(response, (303,), "reset de senha")

            response = client.post(
                "/access-profiles/new",
                data={"name": f"Perfil {marker}", "description": "Perfil de auditoria", "is_active": "on"},
                follow_redirects=False,
            )
            expect(response, (303,), "cadastro de perfil")
            db = SessionLocal()
            try:
                profile_id = db.query(AccessProfile).filter(AccessProfile.name == f"Perfil {marker}").one().id
            finally:
                db.close()
            response = client.post(
                f"/access-profiles/{profile_id}/edit",
                data={"name": f"Perfil Editado {marker}", "description": "Perfil editado", "is_active": "on"},
                follow_redirects=False,
            )
            expect(response, (303,), "edição de perfil")
            response = client.post(f"/access-profiles/{profile_id}/deactivate", follow_redirects=False)
            expect(response, (303,), "desativação de perfil")

            for index in (1, 2, 3):
                content = (
                    f"CONTRATO {marker}-{index}\n"
                    f"Operadora: {operator_name}\n"
                    "Prazo de pagamento: 30 dias\n"
                    "Reajuste anual pelo IPCA\n"
                ).encode()
                response = client.post(
                    "/contracts/import",
                    data={"operator_name": operator_name, "import_mode": "contract"},
                    files={"file": (f"{marker}-{index}.txt", BytesIO(content), "text/plain")},
                )
                expect(response, (200,), f"upload do contrato {index}")
                contract_ids.append(response.json()["id"])

            response = client.post(
                f"/contracts/{contract_ids[0]}/edit",
                data={
                    "contract_name": f"Contrato editado {marker}",
                    "operator_name": operator_name,
                    "contract_number": f"{marker}-EDIT",
                    "payment_term_days": "25",
                    "reajust_clause_exists": "on",
                    "reajust_index": "IPCA",
                },
                follow_redirects=False,
            )
            expect(response, (303,), "edição de contrato")
            expect(client.get(f"/contracts/{contract_ids[0]}"), (200,), "tela de detalhe do contrato")

            response = client.post(
                f"/contracts/{contract_ids[0]}/events",
                data={"event_type": "nota", "title": f"Evento {marker}", "notes": "Persistência validada."},
                follow_redirects=False,
            )
            expect(response, (303,), "evento contratual")

            response = client.post(
                f"/contracts/{contract_ids[0]}/additional",
                data={"responsible_name": "Responsável Persistente", "contact_info": "audit@example.local", "adjustment_type": "IPCA"},
                follow_redirects=False,
            )
            expect(response, (303,), "cadastro adicional")

            response = client.post(f"/analises-ia/run?contract_id={contract_ids[0]}")
            expect(response, (200,), "análise do contrato")

            response = client.post(
                "/contracts/import",
                data={"operator_name": operator_name, "import_mode": "additive"},
                files={"file": (f"ADITIVO-{marker}.txt", BytesIO(b"ADITIVO CONTRATUAL\nReajuste IPCA"), "text/plain")},
            )
            expect(response, (200,), "upload de aditivo")

            response = client.post(
                "/comparacoes",
                data={"title": f"Comparação {marker}", "contract_ids": [str(value) for value in contract_ids[:2]]},
                follow_redirects=False,
            )
            expect(response, (303,), "comparação de contratos")
            expect(client.get("/comparacoes"), (200,), "listagem de comparações")

            response = client.post(f"/contracts/{contract_ids[1]}/delete", follow_redirects=False)
            expect(response, (303,), "exclusão de contrato")

            response = client.post(
                "/change-password",
                data={"current_password": "Audit!1234", "new_password": "Audit!9876", "new_password_confirm": "Audit!9876"},
            )
            expect(response, (200,), "troca de senha")

            response = client.post(f"/users/{created_user_ids[-1]}/deactivate", follow_redirects=False)
            expect(response, (303,), "desativação de usuário")

        # Uma nova instância do cliente simula a reinicialização da aplicação.
        with TestClient(app) as restarted_client:
            restarted_client.headers["Origin"] = "http://testserver"
            expect(restarted_client.get("/health"), (200,), "reinicialização da aplicação")

        db = SessionLocal()
        try:
            created_user = db.query(User).filter(User.username == f"{username}-user").one()
            assert created_user.full_name == "Usuário Persistente Editado"
            assert created_user.is_active is False
            assert db.query(AccessProfile).filter(AccessProfile.id == profile_id, AccessProfile.is_active.is_(False)).count() == 1
            assert db.query(Contract).filter(Contract.id.in_(contract_ids)).count() == 2
            assert db.query(Contract).filter(Contract.id == contract_ids[0], Contract.contract_number == f"{marker}-EDIT").count() == 1
            assert db.query(Contract).filter(Contract.id == contract_ids[0], Contract.responsible_name == "Responsável Persistente").count() == 1
            assert db.query(ContractEvent).filter(ContractEvent.contract_id == contract_ids[0]).count() == 1
            assert db.query(AIAnalysis).filter(AIAnalysis.contract_id == contract_ids[0]).count() >= 2
            assert db.query(ContractAdditive).filter(ContractAdditive.contract_id.in_(contract_ids)).count() == 1
            assert db.query(ContractComparison).filter(ContractComparison.title == f"Comparação {marker}").count() == 1
        finally:
            db.close()

        print("AUDITORIA DE PERSISTENCIA: OK")
        print("Usuarios, perfis, contratos, upload, edicao, exclusao, evento, analise, aditivo, comparacao e senhas persistiram apos reinicializacao.")
    finally:
        db = SessionLocal()
        try:
            db.query(ContractComparison).filter(ContractComparison.title == f"Comparação {marker}").delete(synchronize_session=False)
            db.query(Contract).filter(Contract.id.in_(contract_ids)).delete(synchronize_session=False)
            db.query(ImportBatch).filter(ImportBatch.original_filename.like(f"%{marker}%")).delete(synchronize_session=False)
            db.query(User).filter(User.username.like(f"{username}%")).delete(synchronize_session=False)
            if profile_id:
                db.query(AccessProfile).filter(AccessProfile.id == profile_id).delete(synchronize_session=False)
            operator = db.query(Operator).filter(Operator.name == operator_name).first()
            if operator and not operator.contracts:
                db.delete(operator)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        for path in Path("uploads").rglob(f"*{marker}*"):
            if path.is_file():
                path.unlink()


if __name__ == "__main__":
    main()
