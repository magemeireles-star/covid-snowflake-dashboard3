# covid_dashboard.py
# Dashboard COVID-19 — Streamlit + Snowflake
# Dados: Our World in Data (OWID)
# Atividade prática de Ciência de Dados

import streamlit as st
import pandas as pd
import plotly.express as px
from snowflake.snowpark import Session

# ----------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard COVID-19 — OWID + Snowflake",
    page_icon="🦠",
    layout="wide",
)

# ----------------------------------------------------------------------
# CONSTANTES
# ----------------------------------------------------------------------
URL_CSV = (
    "https://raw.githubusercontent.com/owid/covid-19-data/"
    "master/public/data/owid-covid-data.csv"
)

# Países que serão analisados. Sinta-se livre para trocar.
PAISES = ["Brazil", "United States", "India", "Germany", "South Africa", "Japan"]

# Data mínima (recorte para acelerar a carga). Coloque "" para não filtrar.
DATA_INICIAL = "2021-01-01"

# Apenas as colunas que realmente vamos usar (acelera muito o download/carga).
COLUNAS = [
    "location", "continent", "date",
    "total_cases", "new_cases",
    "total_deaths", "new_deaths",
    "population",
    "people_vaccinated", "people_fully_vaccinated", "total_vaccinations",
]

TABELA = "COVID_DATA"  # nome da tabela no Snowflake

# Parâmetros de conexão lidos do secrets.toml
connection_parameters = {
    "user": st.secrets["snowflake"]["user"],
    "password": st.secrets["snowflake"]["password"],
    "account": st.secrets["snowflake"]["account"],
    "warehouse": st.secrets["snowflake"]["warehouse"],
    "database": "TEST_DB",
    "schema": "PUBLIC",
    "role": st.secrets["snowflake"]["role"],
}


# ----------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ----------------------------------------------------------------------
@st.cache_resource
def get_session() -> Session:
    """Cria (uma única vez) a sessão Snowpark com o Snowflake."""
    return Session.builder.configs(connection_parameters).create()


def baixar_e_filtrar() -> pd.DataFrame:
    """Baixa o CSV da OWID, mantém só os países/colunas/período escolhidos."""
    df = pd.read_csv(URL_CSV, usecols=COLUNAS)
    df = df[df["location"].isin(PAISES)]
    if DATA_INICIAL:
        df = df[df["date"] >= DATA_INICIAL]
    # Garante tipos numéricos limpos e remove a coluna de data como texto padrão
    df = df.reset_index(drop=True)
    return df


def carregar_no_snowflake():
    """Baixa, filtra e grava a tabela no Snowflake (cria/sobrescreve)."""
    session = get_session()
    df = baixar_e_filtrar()
    # Colunas em MAIÚSCULAS para casar com o padrão do Snowflake
    df.columns = [c.upper() for c in df.columns]
    session.write_pandas(
        df,
        table_name=TABELA,
        auto_create_table=True,
        overwrite=True,
    )
    return len(df)


def ler_do_snowflake() -> pd.DataFrame:
    """Lê a tabela do Snowflake e devolve um DataFrame pandas já normalizado."""
    session = get_session()
    df = session.table(TABELA).to_pandas()
    # Normaliza nomes de coluna para minúsculas (evita dor de cabeça com case)
    df.columns = df.columns.str.lower()
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


df = df.sort_values("date")
       latest = df.groupby("location", as_index=False).last()
       return latest


# ----------------------------------------------------------------------
# SIDEBAR — BOTÕES DE CARGA
# ----------------------------------------------------------------------
st.sidebar.title("⚙️ Controles")
st.sidebar.caption("Países atuais: " + ", ".join(PAISES))

if st.sidebar.button("☁️ Carregar Dados no Snowflake"):
    with st.spinner("Baixando CSV da OWID e gravando no Snowflake..."):
        try:
            n = carregar_no_snowflake()
            st.sidebar.success(f"✅ {n} linhas gravadas na tabela {TABELA}.")
        except Exception as e:
            st.sidebar.error(f"Erro ao carregar: {e}")

if st.sidebar.button("📊 Carregar Dashboard"):
    with st.spinner("Lendo dados do Snowflake..."):
        try:
            st.session_state["df"] = ler_do_snowflake()
            st.sidebar.success("✅ Dados carregados na memória.")
        except Exception as e:
            st.sidebar.error(f"Erro ao ler a tabela: {e}")

# ----------------------------------------------------------------------
# CONTEÚDO PRINCIPAL
# ----------------------------------------------------------------------
st.title("🦠 Dashboard COVID-19 — Our World in Data")
st.caption("Fonte: OWID · Armazenamento: Snowflake · Visualização: Streamlit + Plotly")

if "df" not in st.session_state:
    st.info(
        "👈 Comece clicando em **Carregar Dados no Snowflake** "
        "(só na primeira vez) e depois em **Carregar Dashboard**."
    )
    st.stop()

df = st.session_state["df"]

# ---- Filtro interativo: seleção de países ----
paises_disponiveis = sorted(df["location"].unique())
selecionados = st.multiselect(
    "Filtrar países:",
    options=paises_disponiveis,
    default=paises_disponiveis,
)
if not selecionados:
    st.warning("Selecione pelo menos um país.")
    st.stop()

dff = df[df["location"].isin(selecionados)].copy()
latest = valores_mais_recentes(dff)

# ---- KPIs ----
col1, col2, col3 = st.columns(3)
col1.metric("Total de casos", f"{int(latest['total_cases'].sum()):,}".replace(",", "."))
col2.metric("Total de óbitos", f"{int(latest['total_deaths'].sum()):,}".replace(",", "."))
col3.metric("Países analisados", len(selecionados))

st.divider()

# ---- Abas com as visualizações ----
aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs(
    ["📈 Casos novos", "💀 Óbitos", "💉 Vacinação",
     "🔵 População × Casos", "🗂️ Dados brutos", "🧮 Query SQL"]
)

# 1) Linha — casos novos ao longo do tempo
with aba1:
    st.subheader("Evolução de casos novos ao longo do tempo")
    fig = px.line(dff, x="date", y="new_cases", color="location",
                  labels={"date": "Data", "new_cases": "Novos casos",
                          "location": "País"})
    st.plotly_chart(fig, use_container_width=True)

# 2) Barras — total de óbitos por país
with aba2:
    st.subheader("Total de óbitos por país (valor mais recente)")
    fig = px.bar(latest.sort_values("total_deaths", ascending=False),
                 x="location", y="total_deaths", color="location",
                 labels={"location": "País", "total_deaths": "Total de óbitos"})
    st.plotly_chart(fig, use_container_width=True)

# 3) Pizza — proporção de pessoas vacinadas (1 dose) por país
with aba3:
    st.subheader("Proporção de pessoas vacinadas (≥1 dose) — data mais recente")
    vac = latest.dropna(subset=["people_vaccinated"])
    if vac.empty:
        st.warning("Sem dados de vacinação para os países/período selecionados.")
    else:
        fig = px.pie(vac, names="location", values="people_vaccinated",
                     labels={"location": "País"})
        st.plotly_chart(fig, use_container_width=True)

# 4) Dispersão — população × total de casos
with aba4:
    st.subheader("Relação entre população e total de casos")
    fig = px.scatter(latest, x="population", y="total_cases",
                     color="location", size="total_cases", hover_name="location",
                     labels={"population": "População", "total_cases": "Total de casos",
                             "location": "País"})
    st.plotly_chart(fig, use_container_width=True)

# 5) Dados brutos + download
with aba5:
    st.subheader("Dados brutos")
    st.dataframe(dff, use_container_width=True)
    st.download_button(
        "⬇️ Baixar CSV",
        data=dff.to_csv(index=False).encode("utf-8"),
        file_name="covid_filtrado.csv",
        mime="text/csv",
    )

# 6) (Bônus) Query SQL personalizada no Snowflake
with aba6:
    st.subheader("Executar consulta SQL no Snowflake")
    query = st.text_area(
        "Digite sua query:",
        value=f"SELECT location, MAX(total_cases) AS max_casos "
              f"FROM {TABELA} GROUP BY location ORDER BY max_casos DESC;",
        height=120,
    )
    if st.button("▶️ Executar query"):
        try:
            session = get_session()
            resultado = session.sql(query).to_pandas()
            st.dataframe(resultado, use_container_width=True)
        except Exception as e:
            st.error(f"Erro na query: {e}")
