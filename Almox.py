from datetime import datetime, date
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

# Configuração da Página
st.set_page_config(
    page_title="Sistema de Almoxarifado - Centros de Custo",
    page_icon="📦",
    layout="wide",
)

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---


def init_db():
    conn = sqlite3.connect("almoxarifado.db")
    cursor = conn.cursor()

    # Tabela de Usuários
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            cargo TEXT NOT NULL
        )
    """)

    # Tabela de Centros de Custo / Setores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS centros_custo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT
        )
    """)

    # Tabela de Itens / Estoque
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            estoque_minimo INTEGER NOT NULL,
            valor_unitario REAL NOT NULL,
            data_atualizacao TEXT NOT NULL
        )
    """)

    # Tabela de Movimentacoes (Entradas e Saídas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            setor_id INTEGER,
            tipo TEXT NOT NULL, -- 'Entrada' ou 'Saída'
            quantidade INTEGER NOT NULL,
            usuario TEXT NOT NULL,
            data TEXT NOT NULL,
            observacao TEXT,
            FOREIGN KEY(item_id) REFERENCES itens(id),
            FOREIGN KEY(setor_id) REFERENCES centros_custo(id)
        )
    """)

    # Garantir compatibilidade caso a tabela de movimentações já exista sem setor_id
    cursor.execute("PRAGMA table_info(movimentacoes)")
    columns = [col[1] for col in cursor.fetchall()]
    if "setor_id" not in columns:
        try:
            cursor.execute(
                "ALTER TABLE movimentacoes ADD COLUMN setor_id INTEGER"
            )
        except:
            pass

    # Criar usuário admin padrão se não existir
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO usuarios (username, senha, cargo) VALUES (?, ?, ?)",
            ("admin", "123456", "Administrador"),
        )

    # Criar centro de custo padrão se não existir
    cursor.execute("SELECT COUNT(*) FROM centros_custo")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO centros_custo (codigo, nome, descricao) VALUES (?, ?, ?)",
            ("GER", "Geral / Administrativo", "Setor padrão para uso geral"),
        )

    conn.commit()
    conn.close()


init_db()

# --- FUNÇÕES DE AUXÍLIO ---


def run_query(query, params=()):
    conn = sqlite3.connect("almoxarifado.db")
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()


def get_data(query, params=()):
    conn = sqlite3.connect("almoxarifado.db")
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df


# --- SISTEMA DE AUTENTICAÇÃO ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.cargo = ""

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1.5, 1])

    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.subheader("🔐 Login - Almoxarifado")

        with st.form("form_login"):
            user_input = st.text_input("Usuário")
            senha_input = st.text_input("Senha", type="password")
            submit_login = st.form_submit_button("Entrar", width="stretch")

            if submit_login:
                conn = sqlite3.connect("almoxarifado.db")
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT username, cargo FROM usuarios WHERE username = ? AND senha = ?",
                    (user_input, senha_input),
                )
                user = cursor.fetchone()
                conn.close()

                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = user[0]
                    st.session_state.cargo = user[1]
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

    st.stop()

# --- MENU LATERAL (SISTEMA LOGADO) ---
st.sidebar.title(f"📦 Olá, {st.session_state.username}")
st.sidebar.markdown(f"**Cargo:** {st.session_state.cargo}")
st.sidebar.markdown("---")

menu = st.sidebar.selectbox(
    "Navegação",
    [
        "Dashboard",
        "Gestão de Itens",
        "Centros de Custo / Setores",
        "Entrada / Saída de Estoque",
        "Relatórios",
        "Gerenciar Usuários",
    ],
)

if st.sidebar.button("🚪 Sair do Sistema"):
    st.session_state.logged_in = False
    st.rerun()

# ==================== DASHBOARD ====================
if menu == "Dashboard":
    st.title("📊 Dashboard do Almoxarifado")

    df_itens = get_data("SELECT * FROM itens")
    df_mov = get_data("""
        SELECT m.*, c.nome as setor_nome 
        FROM movimentacoes m
        LEFT JOIN centros_custo c ON m.setor_id = c.id
    """)

    if not df_itens.empty:
        total_itens = df_itens["quantidade"].sum()
        valor_total = (df_itens["quantidade"] * df_itens["valor_unitario"]).sum()
        itens_criticos = len(
            df_itens[df_itens["quantidade"] <= df_itens["estoque_minimo"]]
        )
        total_produtos = len(df_itens)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Produtos (SKUs)", total_produtos)
        col2.metric("Qtd. Total no Estoque", int(total_itens))
        col3.metric("Valor Total em Estoque", f"R$ {valor_total:,.2f}")
        col4.metric(
            "Itens abaixo do Mínimo",
            itens_criticos,
            delta=f"-{itens_criticos}" if itens_criticos > 0 else "Normal",
            delta_color="inverse",
        )

        st.markdown("---")

        c1, c2 = st.columns(2)

        with c1:
            st.subheader("📦 Valor em Estoque por Categoria")
            df_itens["valor_total"] = (
                df_itens["quantidade"] * df_itens["valor_unitario"]
            )
            fig_cat = px.pie(
                df_itens,
                names="categoria",
                values="valor_total",
                hole=0.4,
                title="Distribuição de Valor por Categoria",
            )
            st.plotly_chart(fig_cat, width="stretch")

        with c2:
            st.subheader("🚨 Alerta de Estoque Mínimo")
            df_criticos = df_itens[
                df_itens["quantidade"] <= df_itens["estoque_minimo"]
            ][["codigo", "nome", "quantidade", "estoque_minimo"]]
            if not df_criticos.empty:
                st.dataframe(df_criticos, width="stretch", hide_index=True)
            else:
                st.success(
                    "Todos os itens estão com o estoque acima do mínimo!"
                )
    else:
        st.info("Nenhum item cadastrado no sistema.")

# ==================== GESTÃO DE ITENS ====================
elif menu == "Gestão de Itens":
    st.title("🛠️ Cadastro e Gestão de Itens")

    with st.form("form_item", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            codigo = st.text_input("Código do Item / SKU")
            nome = st.text_input("Nome do Produto")
            categoria = st.text_input("Categoria")
        with col2:
            quantidade = st.number_input(
                "Quantidade Inicial", min_value=0, step=1
            )
            estoque_minimo = st.number_input(
                "Estoque Mínimo", min_value=0, step=1
            )
            valor_unitario = st.number_input(
                "Valor Unitário (R$)", min_value=0.0, format="%.2f"
            )

        submit_item = st.form_submit_button("Cadastrar / Atualizar Item")

        if submit_item:
            if codigo and nome and categoria:
                try:
                    data_hoje = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    run_query(
                        """
                        INSERT INTO itens (codigo, nome, categoria, quantidade, estoque_minimo, valor_unitario, data_atualizacao)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(codigo) DO UPDATE SET 
                        nome=excluded.nome, categoria=excluded.categoria, 
                        quantidade=excluded.quantidade, estoque_minimo=excluded.estoque_minimo, 
                        valor_unitario=excluded.valor_unitario, data_atualizacao=excluded.data_atualizacao
                    """,
                        (
                            codigo,
                            nome,
                            categoria,
                            quantidade,
                            estoque_minimo,
                            valor_unitario,
                            data_hoje,
                        ),
                    )
                    st.success(f"Item '{nome}' salvo com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao salvar item: {e}")
            else:
                st.warning("Preencha todos os campos obrigatórios.")

    st.subheader("Estoque Atual")
    df_estoque = get_data("SELECT * FROM itens")
    if not df_estoque.empty:
        st.dataframe(df_estoque, width="stretch", hide_index=True)
    else:
        st.info("Nenhum item cadastrado.")

# ==================== CENTROS DE CUSTO / SETORES ====================
elif menu == "Centros de Custo / Setores":
    st.title("🏢 Gestão de Centros de Custo / Setores")

    with st.form("form_setor", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            codigo_cc = st.text_input("Código do Centro de Custo (Ex: CC01)")
            nome_cc = st.text_input("Nome do Setor / Centro de Custo")
        with col2:
            desc_cc = st.text_input("Descrição (Opcional)")

        btn_cc = st.form_submit_button("Cadastrar Centro de Custo")

        if btn_cc:
            if codigo_cc and nome_cc:
                try:
                    run_query(
                        """
                        INSERT INTO centros_custo (codigo, nome, descricao)
                        VALUES (?, ?, ?)
                        ON CONFLICT(codigo) DO UPDATE SET 
                        nome=excluded.nome, descricao=excluded.descricao
                    """,
                        (codigo_cc, nome_cc, desc_cc),
                    )
                    st.success(
                        f"Centro de Custo '{nome_cc}' cadastrado com sucesso!"
                    )
                except Exception as e:
                    st.error(f"Erro ao cadastrar centro de custo: {e}")
            else:
                st.warning("Preencha o código e o nome do centro de custo.")

    st.subheader("Centros de Custo Cadastrados")
    df_cc = get_data("SELECT * FROM centros_custo")
    if not df_cc.empty:
        st.dataframe(df_cc, width="stretch", hide_index=True)
    else:
        st.info("Nenhum centro de custo cadastrado.")

# ==================== ENTRADA / SAÍDA DE ESTOQUE ====================
elif menu == "Entrada / Saída de Estoque":
    st.title("🔄 Movimentações de Estoque")

    tab1, tab2 = st.tabs(["📥 Registrar Entrada", "📤 Registrar Saída"])

    itens_df = get_data("SELECT id, codigo, nome, quantidade FROM itens")
    setores_df = get_data("SELECT id, codigo, nome FROM centros_custo")

    if itens_df.empty:
        st.warning("Cadastre itens primeiro na aba 'Gestão de Itens'.")
    else:
        item_dict = {
            f"{row['codigo']} - {row['nome']} (Atual: {row['quantidade']})": row[
                "id"
            ]
            for _, row in itens_df.iterrows()
        }

        setor_dict = {}
        if not setores_df.empty:
            setor_dict = {
                f"{row['codigo']} - {row['nome']}": row["id"]
                for _, row in setores_df.iterrows()
            }

        with tab1:
            st.subheader("Entrada de Mercadoria")
            with st.form("form_entrada"):
                item_selecionado = st.selectbox(
                    "Selecione o Item (Entrada)",
                    list(item_dict.keys()),
                    key="ent",
                )
                qtd_entrada = st.number_input(
                    "Quantidade de Entrada", min_value=1, step=1
                )
                obs_entrada = st.text_input("Observação / Nota Fiscal")
                btn_ent = st.form_submit_button("Confirmar Entrada")

                if btn_ent:
                    item_id = item_dict[item_selecionado]
                    data_hoje = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    run_query(
                        "UPDATE itens SET quantidade = quantidade + ? WHERE id = ?",
                        (qtd_entrada, item_id),
                    )
                    run_query(
                        """
                        INSERT INTO movimentacoes (item_id, setor_id, tipo, quantidade, usuario, data, observacao)
                        VALUES (?, NULL, 'Entrada', ?, ?, ?, ?)
                    """,
                        (
                            item_id,
                            qtd_entrada,
                            st.session_state.username,
                            data_hoje,
                            obs_entrada,
                        ),
                    )
                    st.success("Entrada registrada com sucesso!")
                    st.rerun()

        with tab2:
            st.subheader("Saída de Mercadoria por Centro de Custo")
            if setores_df.empty:
                st.warning(
                    "Cadastre ao menos um Centro de Custo na aba 'Centros de Custo / Setores'."
                )
            else:
                with st.form("form_saida"):
                    item_selecionado_s = st.selectbox(
                        "Selecione o Item (Saída)",
                        list(item_dict.keys()),
                        key="sai",
                    )
                    setor_selecionado = st.selectbox(
                        "Centro de Custo / Setor Destino",
                        list(setor_dict.keys()),
                    )
                    qtd_saida = st.number_input(
                        "Quantidade de Saída", min_value=1, step=1
                    )
                    obs_saida = st.text_input("Finalidade / Motivo da Saída")
                    btn_sai = st.form_submit_button("Confirmar Saída")

                    if btn_sai:
                        item_id = item_dict[item_selecionado_s]
                        setor_id = setor_dict[setor_selecionado]

                        qtd_atual = get_data(
                            "SELECT quantidade FROM itens WHERE id = ?",
                            (item_id,),
                        ).iloc[0]["quantidade"]

                        if qtd_saida > qtd_atual:
                            st.error(
                                f"Estoque insuficiente! Quantidade atual: {qtd_atual}"
                            )
                        else:
                            data_hoje = datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                            run_query(
                                "UPDATE itens SET quantidade = quantidade - ? WHERE id = ?",
                                (qtd_saida, item_id),
                            )
                            run_query(
                                """
                                INSERT INTO movimentacoes (item_id, setor_id, tipo, quantidade, usuario, data, observacao)
                                VALUES (?, ?, 'Saída', ?, ?, ?, ?)
                            """,
                                (
                                    item_id,
                                    setor_id,
                                    qtd_saida,
                                    st.session_state.username,
                                    data_hoje,
                                    obs_saida,
                                ),
                            )
                            st.success(
                                "Saída registrada para o centro de custo com sucesso!"
                            )
                            st.rerun()

# ==================== RELATÓRIOS ====================
elif menu == "Relatórios":
    st.title("📈 Relatórios e Custos por Setor")

    tab_r1, tab_r2, tab_r3 = st.tabs(
        [
            "📋 Posição de Estoque",
            "📊 Saídas por Centro de Custo",
            "📜 Histórico Geral",
        ]
    )

    with tab_r1:
        st.subheader("Posição Atual do Estoque")
        df_geral = get_data("SELECT * FROM itens")
        if not df_geral.empty:
            df_geral["valor_total_item"] = (
                df_geral["quantidade"] * df_geral["valor_unitario"]
            )
            st.dataframe(df_geral, width="stretch", hide_index=True)

            csv = df_geral.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Baixar Relatório de Estoque (CSV)",
                data=csv,
                file_name="estoque_atual.csv",
                mime="text/csv",
            )
        else:
            st.info("Sem dados para exibir.")

    with tab_r2:
        st.subheader("Consumo / Saídas por Centro de Custo (Filtrado por Data)")

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            data_inicio = st.date_input(
                "Data Inicial", date.today().replace(day=1), key="d_ini_cc"
            )
        with col_d2:
            data_fim = st.date_input("Data Final", date.today(), key="d_fim_cc")

        df_cc_report = get_data(
            """
            SELECT c.codigo as codigo_cc, c.nome as centro_custo, i.nome as produto, 
                   m.quantidade, i.valor_unitario, (m.quantidade * i.valor_unitario) as valor_total_saida,
                   m.usuario, m.data, m.observacao
            FROM movimentacoes m
            JOIN centros_custo c ON m.setor_id = c.id
            JOIN itens i ON m.item_id = i.id
            WHERE m.tipo = 'Saída' AND DATE(m.data) BETWEEN ? AND ?
            ORDER BY m.data DESC
        """,
            (data_inicio.strftime("%Y-%m-%d"), data_fim.strftime("%Y-%m-%d")),
        )

        if not df_cc_report.empty:
            st.dataframe(df_cc_report, width="stretch", hide_index=True)

            st.markdown("### 📊 Gráfico de Custos por Setor no Período (R$)")
            df_resumo_cc = (
                df_cc_report.groupby("centro_custo")["valor_total_saida"]
                .sum()
                .reset_index()
            )
            fig_cc = px.bar(
                df_resumo_cc,
                x="centro_custo",
                y="valor_total_saida",
                text="valor_total_saida",
                labels={
                    "centro_custo": "Centro de Custo",
                    "valor_total_saida": "Valor Total Consumido (R$)",
                },
                color="centro_custo",
            )
            fig_cc.update_traces(
                texttemplate="R$ %{text:.2f}", textposition="outside"
            )
            st.plotly_chart(fig_cc, width="stretch")

            csv_cc = df_cc_report.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Baixar Relatório Filtrado por Centro de Custo (CSV)",
                data=csv_cc,
                file_name="saidas_por_centro_custo_filtrado.csv",
                mime="text/csv",
            )
        else:
            st.info(
                "Nenhuma saída registrada para o período e centros de custo selecionados."
            )

    with tab_r3:
        st.subheader("Histórico Completo de Movimentações (Filtrado por Data)")

        col_hd1, col_hd2 = st.columns(2)
        with col_hd1:
            data_inicio_h = st.date_input(
                "Data Inicial (Histórico)",
                date.today().replace(day=1),
                key="d_ini_h",
            )
        with col_hd2:
            data_fim_h = st.date_input(
                "Data Final (Histórico)", date.today(), key="d_fim_h"
            )

        df_movs = get_data(
            """
            SELECT m.id, i.codigo as cod_item, i.nome as item, m.tipo, m.quantidade, 
                   COALESCE(c.nome, 'N/A') as centro_custo, m.usuario, m.data, m.observacao
            FROM movimentacoes m
            JOIN itens i ON m.item_id = i.id
            LEFT JOIN centros_custo c ON m.setor_id = c.id
            WHERE DATE(m.data) BETWEEN ? AND ?
            ORDER BY m.data DESC
        """,
            (
                data_inicio_h.strftime("%Y-%m-%d"),
                data_fim_h.strftime("%Y-%m-%d"),
            ),
        )

        if not df_movs.empty:
            st.dataframe(df_movs, width="stretch", hide_index=True)

            csv_mov = df_movs.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Baixar Histórico Filtrado (CSV)",
                data=csv_mov,
                file_name="historico_movimentacoes_filtrado.csv",
                mime="text/csv",
            )
        else:
            st.info("Nenhuma movimentação registrada no período selecionado.")

# ==================== GERENCIAR USUÁRIOS ====================
elif menu == "Gerenciar Usuários":
    st.title("👥 Gerenciamento de Acesso")

    if st.session_state.cargo != "Administrador":
        st.warning(
            "Apenas usuários com cargo de Administrador podem gerenciar acessos."
        )
    else:
        with st.form("form_novo_usuario"):
            nuevo_user = st.text_input("Novo Usuário")
            nova_senha = st.text_input("Senha", type="password")
            cargo = st.selectbox(
                "Cargo", ["Administrador", "Operador de Almoxarifado"]
            )
            btn_cad_user = st.form_submit_button("Cadastrar Usuário")

            if btn_cad_user:
                if nuevo_user and nova_senha:
                    try:
                        run_query(
                            "INSERT INTO usuarios (username, senha, cargo) VALUES (?, ?, ?)",
                            (nuevo_user, nova_senha, cargo),
                        )
                        st.success(f"Usuário '{nuevo_user}' criado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro (Nome de usuário já existe?): {e}")
                else:
                    st.warning("Preencha todos os campos.")

        st.subheader("Usuários Cadastrados")
        st.dataframe(
            get_data("SELECT id, username, cargo FROM usuarios"),
            width="stretch",
            hide_index=True,
        )