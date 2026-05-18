import os
from fpdf import FPDF
from utils.db import SessionLocal
from models.contract import Contract
from models.client import Client


def gerar_pdf_contrato(contrato_id: int, destino="contrato.pdf"):
    db = SessionLocal()
    try:
        c = db.get(Contract, contrato_id)
        cli = db.get(Client, c.cliente_id) if c else None
    finally:
        db.close()

    # Cores do sistema
    COR_ROSA = (213, 156, 156)
    COR_ROSA_CLARO = (255, 240, 238)
    COR_BRANCO = (255, 255, 255)
    COR_TEXTO = (74, 48, 48)

    class PDFContrato(FPDF):
        def header(self):
            self.set_fill_color(*COR_ROSA_CLARO)
            self.rect(0, 0, 210, 297, 'F')
            self.set_fill_color(245, 220, 220)
            self.rect(0, 0, 210, 60, 'F')
            try:
                possiveis_caminhos = [
                    os.path.join(os.path.dirname(__file__), "..", "ui", "logogf.png"),
                    os.path.join(os.path.dirname(__file__), "..", "assets", "logogf.png"),
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

    pdf = PDFContrato()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=30)

    # Título
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*COR_ROSA)
    pdf.cell(0, 10, "CONTRATO DE PRESTAÇÃO DE SERVIÇOS", ln=True, align="C")
    pdf.ln(5)

    # Linha decorativa
    pdf.set_draw_color(*COR_ROSA)
    pdf.set_line_width(0.5)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(10)

    # Dados do cliente
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*COR_TEXTO)
    pdf.cell(0, 8, f"{cli.nome if cli else ''}", ln=True)
    pdf.cell(0, 8, f"CPF: {cli.cpf if cli else '—'}", ln=True)
    if cli and cli.telefone:
        pdf.cell(0, 8, f"Telefone: {cli.telefone}", ln=True)
    if cli and cli.email:
        pdf.cell(0, 8, f"E-mail: {cli.email}", ln=True)
    pdf.ln(8)

    # Dados do contrato
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*COR_ROSA)
    pdf.cell(0, 8, "DADOS DO CONTRATO", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COR_TEXTO)
    pdf.cell(0, 6, f"Tratamento: {c.tipo_tratamento if c else '—'}", ln=True)
    pdf.cell(0, 6, f"Valor total: R$ {c.valor:.2f}" if c else "Valor: —", ln=True)
    if c and c.forma_pagamento:
        pdf.cell(0, 6, f"Forma de pagamento: {c.forma_pagamento}", ln=True)
    if c and c.parcelamento:
        pdf.cell(0, 6, f"Parcelamento: {c.parcelamento}", ln=True)
    pdf.ln(8)

    # Cláusulas
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*COR_ROSA)
    pdf.cell(0, 8, "CLÁUSULAS CONTRATUAIS", ln=True)
    pdf.ln(2)

    clausulas = [
        "1) A contratante declara estar ciente dos protocolos de tratamento a serem aplicados,",
        "   bem como dos possíveis efeitos e reações.",
        "2) A profissional aplicará o tratamento conforme avaliação prévia e boas práticas clínicas.",
        "3) Em caso de cancelamento ou reagendamento, a contratante deverá avisar com no mínimo",
        "   24 horas de antecedência.",
        "4) O não comparecimento sem aviso prévio poderá acarretar a cobrança de taxa de ausência",
        "   conforme combinado.",
        "5) Os resultados dos tratamentos estéticos podem variar de acordo com características",
        "   individuais de cada organismo.",
        "6) A assinatura deste contrato implica concordância integral com todos os termos acima.",
    ]

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COR_TEXTO)
    for linha in clausulas:
        pdf.cell(0, 5, linha, ln=True)
    pdf.ln(8)

    # Termo de Responsabilidade
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*COR_ROSA)
    pdf.cell(0, 8, "TERMO DE RESPONSABILIDADE", ln=True)
    pdf.ln(2)

    nome_cli = cli.nome if cli else "___________________________"
    cpf_cli = cli.cpf if cli else "___.___.___-__"

    termo_linhas = [
        f"Eu, {nome_cli}, portador(a) do CPF nº {cpf_cli}, declaro para os devidos fins que:",
        "",
        "• Fui devidamente informada sobre o tratamento a ser realizado, seus objetivos, técnicas",
        "  empregadas, possíveis reações e cuidados pós-procedimento.",
        "• Autorizo a execução do tratamento acima especificado e assumo a responsabilidade pelo",
        "  cumprimento das orientações fornecidas.",
        "• Declaro que as informações de saúde fornecidas são verdadeiras e completas, isentando",
        "  a profissional de responsabilidade por omissões ou informações incorretas.",
        "• Estou ciente de que resultados podem variar individualmente e que a eficácia do",
        "  tratamento depende também da minha adesão às recomendações pós-procedimento.",
    ]

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COR_TEXTO)
    for linha in termo_linhas:
        pdf.cell(0, 5, linha, ln=True)
    pdf.ln(12)

    # Assinaturas
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "Local e data: _____________________________, ____/____/________", ln=True)
    pdf.ln(10)

    # Linhas de assinatura
    y_atual = pdf.get_y()
    pdf.line(20, y_atual, 95, y_atual)
    pdf.line(115, y_atual, 190, y_atual)
    pdf.ln(2)

    pdf.cell(0, 6, f"{nome_cli}", ln=True)
    pdf.cell(0, 6, f"CPF: {cpf_cli}", ln=True)
    pdf.set_xy(115, y_atual + 2)
    pdf.cell(0, 6, "Profissional Responsável", ln=True)

    if c and c.assinatura_digital:
        pdf.ln(10)
        pdf.set_font("Helvetica-Oblique", 9)
        pdf.cell(0, 6, f"Assinatura digital registrada: {c.assinatura_digital}", ln=True)

    pdf.output(destino)
    return os.path.abspath(destino)
