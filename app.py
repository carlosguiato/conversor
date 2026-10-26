import io
import numpy as np
import pandas as pd
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Conversor de Extrato - Hachimitsu",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilização CSS para remover elementos padrão do Streamlit e refinar o visual
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Cabeçalho Principal Atualizado
st.title("📊 Conversor de Extratos - Hachimitsu")
st.markdown("Faça o upload do extrato bancário para gerar o arquivo CSV.")
st.markdown("---")

# 1. Upload do arquivo dentro de um container elegante
with st.container(border=True):
  st.subheader("📁 Importação de Dados")
  uploaded_file = st.file_uploader(
      "Selecione o arquivo Excel do extrato (.xlsx, .xls)", type=["xlsx", "xls"]
  )

if uploaded_file is not None:
  try:
    # Leitura inicial do arquivo Excel
    df = pd.read_excel(uploaded_file, header=0, skiprows=[1])

    with st.expander("🔍 Ver colunas identificadas na planilha"):
      st.write(df.columns.tolist())

    # Descobre quais contas bancárias existem na coluna 'Conta bancária'
    contas_encontradas = []
    if "Conta bancária" in df.columns:
      contas_encontradas = df["Conta bancária"].dropna().unique()

    st.markdown("---")

    # Bloco de configuração dentro de um container com borda (Título ajustado)
    with st.container(border=True):
      st.subheader("⚙️ Configuração das contas")

      # Mapeamento dinâmico dos bancos encontrados
      mapeamento_contas = {}
      if len(contas_encontradas) > 0:
        for conta in contas_encontradas:
          mapeamento_contas[conta] = st.text_input(
              f"Código da conta do banco **'{conta}'** no Domínio:", value=""
          )
      else:
        st.warning(
            "A coluna 'Conta bancária' não foi encontrada. Será usada a conta"
            " padrão '9'."
        )

      # Configuração das contas transitórias
      col1, col2 = st.columns(2)
      with col1:
        conta_fornecedor = st.text_input(
            "Contra conta para **SAÍDAS** (Fornecedor / < 0):", value=""
        )
      with col2:
        conta_cliente = st.text_input(
            "Contra conta para **ENTRADAS** (Clientes / > 0):", value=""
        )

    st.markdown("---")

    # Botão para processar centralizado e em destaque
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
      processar_clicado = st.button(
          "🚀 Processar e Gerar CSV", type="primary", use_container_width=True
      )

    if processar_clicado:
      if not conta_fornecedor or not conta_cliente:
        st.error(
            "Por favor, preencha as contas transitórias de Fornecedor e Cliente"
            " antes de continuar."
        )
      else:
        # 2. Tratamento da coluna VALOR
        if pd.api.types.is_numeric_dtype(df["Valor"]):
          df["VALOR_NUM"] = df["Valor"].fillna(0)
        else:
          df["VALOR_NUM"] = (
              df["Valor"]
              .astype(str)
              .str.replace(".", "", regex=False)
              .str.replace(",", ".", regex=False)
          )
          df["VALOR_NUM"] = pd.to_numeric(
              df["VALOR_NUM"], errors="coerce"
          ).fillna(0)

        # 3. Lógica Contábil Dinâmica
        def define_debito(row):
          valor = row["VALOR_NUM"]
          if valor < 0:
            return conta_fornecedor
          else:
            banco_linha = row.get("Conta bancária")
            return mapeamento_contas.get(banco_linha, "9")

        def define_credito(row):
          valor = row["VALOR_NUM"]
          if valor < 0:
            banco_linha = row.get("Conta bancária")
            return mapeamento_contas.get(banco_linha, "9")
          else:
            return conta_cliente

        df["Conta Debito"] = df.apply(define_debito, axis=1)
        df["Conta Credito"] = df.apply(define_credito, axis=1)

        # 4. Formatação do Histórico (Limpando nulos e o 'nan')
        def limpar_texto(valor):
          if (
              pd.isna(valor)
              or str(valor).strip().lower() in ["nan", "none", "nat", ""]
          ):
            return ""
          return str(valor).strip()

        df["Historico"] = (
            df["Descrição"].apply(limpar_texto)
            + " - "
            + df["Cliente"].apply(limpar_texto)
            + " - "
            + df["Nr. doc."].apply(limpar_texto)
            + " - "
            + df["Categoria"].apply(limpar_texto)
        )
        df["Historico"] = (
            df["Historico"]
            .str.replace(r"\s*-\s*-\s*", " - ", regex=True)
            .str.strip(" -")
        )

        # 5. Montagem do layout final
        df_final = pd.DataFrame({
            "Data": pd.to_datetime(df["Data"], dayfirst=True).dt.strftime(
                "%d/%m/%Y"
            ),
            "Conta Debito": df["Conta Debito"],
            "Conta Credito": df["Conta Credito"],
            "Valor": df["VALOR_NUM"].abs(),
            "Historico": df["Historico"],
        })

        # Armazenamos também o valor com sinal para calcular separadamente Entradas e Saídas
        df_final["Valor_Com_Sinal"] = df["VALOR_NUM"]

        # 6. Geração do CSV em memória com delimitador ponto e vírgula (sep=';')
        csv_buffer = io.StringIO()
        df_final.drop(columns=["Valor_Com_Sinal"]).to_csv(
            csv_buffer, sep=";", index=False, decimal=",", encoding="cp1252"
        )
        csv_data = csv_buffer.getvalue()

        st.success("✨ Arquivo convertido com sucesso!")

        # Métricas de resumo executivo divididas (Total de lançamentos, Entradas e Saídas)
        m1, m2, m3 = st.columns(3)

        with m1:
          st.metric("Total de Lançamentos", len(df_final))

        with m2:
          total_entradas = df_final[df_final["Valor_Com_Sinal"] > 0][
              "Valor"
          ].sum()
          st.metric(
              "Total de Entradas",
              f"R$ {total_entradas:,.2f}".replace(",", "X")
              .replace(".", ",")
              .replace("X", "."),
          )

        with m3:
          total_saidas = df_final[df_final["Valor_Com_Sinal"] < 0][
              "Valor"
          ].sum()
          st.metric(
              "Total de Saídas",
              f"R$ {total_saidas:,.2f}".replace(",", "X")
              .replace(".", ",")
              .replace("X", "."),
          )

        # Mostra uma prévia na tela dentro de um container
        with st.container(border=True):
          st.subheader("👀 Prévia dos Primeiros Lançamentos")
          st.dataframe(
              df_final.drop(columns=["Valor_Com_Sinal"]).head(15),
              use_container_width=True,
          )

        # Botão de Download em largura total
        st.download_button(
            label="📥 Baixar Arquivo CSV para o Domínio",
            data=csv_data.encode("cp1252", errors="replace"),
            file_name="extrato_pronto_dominio.csv",
            mime="text/csv",
            use_container_width=True,
        )

  except Exception as e:
    st.error(f"Ocorreu um erro ao processar o arquivo: {e}")