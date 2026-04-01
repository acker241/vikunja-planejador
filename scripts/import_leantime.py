#!/usr/bin/env python3
"""
Importador de tarefas do Manual Operacional para Leantime.

Le o Excel 'Manual_Operacional_Associacao_v1.xlsx' e cria projetos/tarefas
no Leantime via JSON-RPC API.

Uso:
    py scripts/import_leantime.py --url https://SEU-DOMINIO.up.railway.app --api-key SUA_API_KEY

Pre-requisitos:
    pip install openpyxl requests

Nota: A API key e criada em Leantime > Company Settings > API
"""

import argparse
import io
import sys
import json
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import openpyxl
import requests


EXCEL_FILE = Path(__file__).parent.parent / "Manual_Operacional_Associacao_v1.xlsx"

# Leantime priorities: 1=Low, 2=Medium, 3=High, 4=Urgent
PRIORITY_MAP = {
    "URGENTE": "urgent",
    "ALTA": "high",
    "MEDIA": "medium",
    "MÉDIA": "medium",
    "BAIXA": "low",
}

STATUS_MAP_DONE = {
    "Concluído": True,
    "🟢 Concluído": True,
    "🟢": True,
}


# ──────────────────────────────────────────────
# Leantime JSON-RPC Client
# ──────────────────────────────────────────────

class LeantimeClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/jsonrpc"
        self.session = requests.Session()
        self.session.headers["x-api-key"] = api_key
        self.session.headers["Content-Type"] = "application/json"
        self._rpc_id = 0

    def _call(self, method: str, params: dict = None) -> dict:
        self._rpc_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._rpc_id,
        }
        if params:
            payload["params"] = params

        resp = self.session.post(self.api_url, json=payload)
        resp.raise_for_status()
        result = resp.json()

        if "error" in result:
            raise Exception(f"RPC Error: {result['error']}")

        return result.get("result")

    def test_connection(self):
        """Testa a conexao e retorna info."""
        try:
            result = self._call("leantime.rpc.projects.getAll")
            print(f"  Conexao OK. Projetos existentes: {len(result) if result else 0}")
            return True
        except Exception as e:
            print(f"  Erro de conexao: {e}")
            return False

    def create_project(self, name: str, details: str = "", client_id: int = 0) -> int:
        """Cria um projeto e retorna o ID."""
        params = {
            "name": name,
            "details": details,
            "type": "project",
        }
        if client_id:
            params["clientId"] = client_id

        result = self._call("leantime.rpc.projects.addProject", params)
        project_id = int(result) if result else 0
        print(f"  Projeto criado: {name} (id={project_id})")
        return project_id

    def create_ticket(self, project_id: int, headline: str, description: str = "",
                      priority: str = "medium", status: str = "3",
                      tags: str = "", ticket_type: str = "task",
                      done: bool = False) -> int:
        """Cria um ticket/tarefa e retorna o ID."""
        params = {
            "headline": headline[:255],
            "description": description,
            "projectId": project_id,
            "priority": priority,
            "status": status,
            "type": ticket_type,
            "tags": tags,
        }

        result = self._call("leantime.rpc.tickets.addTicket", params)
        ticket_id = int(result) if result else 0

        # Mark as done if needed
        if done and ticket_id:
            try:
                self._call("leantime.rpc.tickets.patchTicket", {
                    "id": ticket_id,
                    "status": "0",  # 0 = done in Leantime
                })
            except Exception:
                pass  # best effort

        return ticket_id

    def get_projects(self) -> list:
        """Lista projetos."""
        return self._call("leantime.rpc.projects.getAll") or []


# ──────────────────────────────────────────────
# Excel Parsers (reutilizados do import_vikunja)
# ──────────────────────────────────────────────

def safe_str(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def parse_tarefas_por_pessoa(wb) -> list:
    ws = wb["16_TAREFAS_POR_PESSOA"]
    tasks = []

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True):
        row_list = list(row)
        if len(row_list) >= 11:
            cell_id = safe_str(row_list[1])
            if cell_id and "-" in cell_id and len(cell_id) <= 5:
                responsavel = safe_str(row_list[2])
                tarefa = safe_str(row_list[3])
                prazo = safe_str(row_list[4])
                status = safe_str(row_list[5])
                prioridade = safe_str(row_list[6])
                entregavel = safe_str(row_list[7])
                depende_de = safe_str(row_list[8])
                obs = safe_str(row_list[9])

                titulo_lines = tarefa.split("\n")
                titulo = f"[{cell_id}] {titulo_lines[0]}"
                detalhes = "\n".join(titulo_lines[1:]) if len(titulo_lines) > 1 else ""

                desc = f"<h3>Responsavel: {responsavel}</h3>\n"
                desc += f"<p><strong>Prazo:</strong> {prazo} | <strong>Status:</strong> {status} | <strong>Prioridade:</strong> {prioridade}</p>\n"
                if detalhes:
                    desc += f"<h4>O que fazer</h4>\n<pre>{detalhes}</pre>\n"
                if entregavel:
                    desc += f"<h4>Entregaveis</h4>\n<pre>{entregavel}</pre>\n"
                if depende_de and depende_de != "—":
                    desc += f"<h4>Dependencias</h4>\n<p>{depende_de}</p>\n"
                if obs:
                    desc += f"<h4>Observacoes</h4>\n<p>{obs}</p>\n"

                done = STATUS_MAP_DONE.get(status, False)

                # Map priority
                prio = "medium"
                for key, val in PRIORITY_MAP.items():
                    if key in prioridade.upper():
                        prio = val
                        break

                tags = ",".join(filter(None, [responsavel, prioridade.replace(" ", "")]))

                tasks.append({
                    "title": titulo,
                    "description": desc,
                    "done": done,
                    "priority": prio,
                    "tags": tags,
                    "type": "task",
                })

    return tasks


def parse_cronograma(wb) -> list:
    ws = wb["02_CRONOGRAMA_GERAL"]
    tasks = []

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True):
        row_list = list(row)
        if len(row_list) >= 10:
            num = safe_str(row_list[1])
            if num and num.isdigit():
                atividade = safe_str(row_list[2])
                responsavel = safe_str(row_list[3])
                prerequisito = safe_str(row_list[4])
                obs = safe_str(row_list[9])

                semanas = []
                for i, sem in enumerate([5, 6, 7, 8], 1):
                    if row_list[sem]:
                        semanas.append(f"Sem {i}")

                desc = f"<p><strong>Responsavel:</strong> {responsavel}</p>\n"
                if prerequisito and prerequisito != "—":
                    desc += f"<p><strong>Pre-requisito:</strong> {prerequisito}</p>\n"
                if semanas:
                    desc += f"<p><strong>Periodo:</strong> {', '.join(semanas)}</p>\n"
                if obs:
                    desc += f"<h4>Observacoes</h4>\n<p>{obs}</p>\n"

                tags = responsavel if responsavel else ""

                tasks.append({
                    "title": f"{num}. {atividade}",
                    "description": desc,
                    "done": False,
                    "priority": "medium",
                    "tags": tags,
                    "type": "milestone",
                })

    return tasks


def parse_checklist_cartorio(wb) -> list:
    ws = wb["03_CHECKLIST_CARTORIO"]
    tasks = []

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True):
        row_list = list(row)
        if len(row_list) >= 7:
            num = row_list[0]
            if num and isinstance(num, (int, float)):
                categoria = safe_str(row_list[1])
                item = safe_str(row_list[2])
                descricao = safe_str(row_list[3])
                status = safe_str(row_list[4])
                responsavel = safe_str(row_list[5])
                obs = safe_str(row_list[6])

                done = status.lower() in ("concluído", "concluido")

                desc = f"<p><strong>Categoria:</strong> {categoria} | <strong>Status:</strong> {status}</p>\n"
                if responsavel and responsavel != "—":
                    desc += f"<p><strong>Responsavel:</strong> {responsavel}</p>\n"
                if descricao:
                    desc += f"<h4>Descricao</h4>\n<p>{descricao}</p>\n"
                if obs:
                    desc += f"<h4>Observacoes</h4>\n<p>{obs}</p>\n"

                tags = ",".join(filter(None, [
                    responsavel if responsavel != "—" else "",
                    categoria.replace(" ", ""),
                ]))

                tasks.append({
                    "title": f"#{int(num)} {item}",
                    "description": desc,
                    "done": done,
                    "priority": "medium",
                    "tags": tags,
                    "type": "task",
                })

    return tasks


def parse_pendencias(wb) -> list:
    ws = wb["14_PENDENCIAS_INSUMO"]
    tasks = []

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True):
        row_list = list(row)
        if len(row_list) >= 7:
            num_raw = safe_str(row_list[1])
            if not num_raw:
                continue
            try:
                num = int(float(num_raw))
            except (ValueError, TypeError):
                continue
            if num < 1 or num > 99:
                continue

            pendencia = safe_str(row_list[2])
            fonte = safe_str(row_list[3])
            criticidade = safe_str(row_list[4])
            responsavel = safe_str(row_list[5])
            obs = safe_str(row_list[6])
            if not pendencia:
                continue

            done = "CONCLU" in criticidade.upper() or "CONCLU" in obs.upper()[:20]

            desc = f"<p><strong>Fonte:</strong> {fonte} | <strong>Criticidade:</strong> {criticidade} | <strong>Responsavel:</strong> {responsavel}</p>\n"
            if obs:
                desc += f"<h4>Observacoes</h4>\n<p>{obs}</p>\n"

            prio = "high" if "ALTA" in criticidade.upper() else "medium"
            tags = ",".join(filter(None, [responsavel, "BLOQUEANTE" if "BLOQ" in obs.upper() else ""]))

            tasks.append({
                "title": f"Pendencia #{num}: {pendencia}",
                "description": desc,
                "done": done,
                "priority": prio,
                "tags": tags,
                "type": "bug",
            })

    return tasks


def parse_riscos(wb) -> list:
    ws = wb["12_RISCOS_CONTROLES"]
    tasks = []

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True):
        row_list = list(row)
        if len(row_list) >= 8:
            num_raw = safe_str(row_list[1])
            if not num_raw:
                continue
            try:
                num = int(float(num_raw))
            except (ValueError, TypeError):
                continue
            if num < 1 or num > 99:
                continue

            risco = safe_str(row_list[2])
            if not risco or risco == "Risco":
                continue

            probabilidade = safe_str(row_list[3])
            impacto = safe_str(row_list[4])
            controle = safe_str(row_list[5])
            responsavel = safe_str(row_list[6])

            desc = f"<p><strong>Probabilidade:</strong> {probabilidade} | <strong>Impacto:</strong> {impacto} | <strong>Responsavel:</strong> {responsavel}</p>\n"
            if controle:
                desc += f"<h4>Controle / Mitigacao</h4>\n<p>{controle}</p>\n"

            prio = "high" if impacto in ("Alto", "Critico", "Crítico") else "medium"
            tags = ",".join(filter(None, [responsavel, f"Impacto-{impacto}"]))

            tasks.append({
                "title": f"Risco #{num}: {risco}",
                "description": desc,
                "done": False,
                "priority": prio,
                "tags": tags,
                "type": "bug",
            })

    return tasks


def parse_cnpj_redesim(wb) -> list:
    ws = wb["04_CNPJ_REDESIM_RFB"]
    tasks = []
    current_phase = ""

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True):
        row_list = list(row)
        if len(row_list) >= 7:
            passo = safe_str(row_list[1])

            if passo.startswith("FASE"):
                current_phase = passo
                continue

            if passo and "." in passo:
                try:
                    float(passo)
                except ValueError:
                    continue

                oque_fazer = safe_str(row_list[2])
                quem = safe_str(row_list[3])
                onde = safe_str(row_list[4])
                obs = safe_str(row_list[6])

                desc = f"<p><strong>Fase:</strong> {current_phase} | <strong>Quem:</strong> {quem} | <strong>Onde:</strong> {onde}</p>\n"
                if obs:
                    desc += f"<h4>Observacoes</h4>\n<p>{obs}</p>\n"

                tags = quem if quem else ""

                tasks.append({
                    "title": f"[{passo}] {oque_fazer[:200]}",
                    "description": desc,
                    "done": False,
                    "priority": "medium",
                    "tags": tags,
                    "type": "task",
                })

    return tasks


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Importar tarefas do Excel para Leantime")
    parser.add_argument("--url", required=True, help="URL do Leantime")
    parser.add_argument("--api-key", required=True, help="API key (Company Settings > API)")
    parser.add_argument("--excel", default=str(EXCEL_FILE), help="Caminho do Excel")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostrar o que seria importado")
    args = parser.parse_args()

    # Carregar Excel
    print(f"\n1. Carregando Excel: {args.excel}")
    wb = openpyxl.load_workbook(args.excel, data_only=True)
    print(f"   Abas encontradas: {len(wb.sheetnames)}")

    # Parsear abas
    print("\n2. Extraindo tarefas...")
    sections = {
        "Tarefas Operacionais": parse_tarefas_por_pessoa(wb),
        "Cronograma Geral": parse_cronograma(wb),
        "Checklist Cartorio": parse_checklist_cartorio(wb),
        "Processo CNPJ-REDESIM": parse_cnpj_redesim(wb),
        "Pendencias e Bloqueios": parse_pendencias(wb),
        "Riscos e Controles": parse_riscos(wb),
    }

    total = sum(len(v) for v in sections.values())
    for name, tasks in sections.items():
        done = sum(1 for t in tasks if t.get("done"))
        print(f"   {name}: {len(tasks)} tarefas ({done} concluidas)")
    print(f"   TOTAL: {total} tarefas")

    if args.dry_run:
        print("\n=== DRY RUN ===")
        for name, tasks in sections.items():
            print(f"\n--- {name} ---")
            for t in tasks:
                s = "DONE" if t.get("done") else "TODO"
                print(f"  [{s}] [{t['priority']}] {t['title'][:80]}")
        return

    # Conectar
    print(f"\n3. Conectando ao Leantime: {args.url}")
    client = LeantimeClient(args.url, args.api_key)
    if not client.test_connection():
        print("Falha na conexao. Verifique URL e API key.")
        sys.exit(1)

    # Criar projetos e importar
    print("\n4. Criando projetos e importando tarefas...")
    total_imported = 0

    for name, tasks in sections.items():
        if not tasks:
            continue

        project_id = client.create_project(
            name=f"{name}",
            details=f"Importado do Manual Operacional — {len(tasks)} tarefas",
        )

        if not project_id:
            print(f"  ERRO: nao conseguiu criar projeto {name}")
            continue

        count_done = 0
        count_todo = 0

        for t in tasks:
            # Map status: Leantime uses 3=New, 1=InProgress, 0=Done
            if t.get("done"):
                lt_status = "0"
                count_done += 1
            else:
                lt_status = "3"
                count_todo += 1

            client.create_ticket(
                project_id=project_id,
                headline=t["title"],
                description=t["description"],
                priority=t["priority"],
                status=lt_status,
                tags=t.get("tags", ""),
                ticket_type=t.get("type", "task"),
                done=t.get("done", False),
            )

        total_imported += len(tasks)
        print(f"  {name}: {count_todo} pendentes, {count_done} concluidas ({len(tasks)} total)")

    print(f"\n{'='*50}")
    print(f"Importacao concluida!")
    print(f"  Projetos: {len(sections)}")
    print(f"  Tarefas importadas: {total_imported}")
    print(f"\nAceda em: {args.url}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
