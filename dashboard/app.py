"""
F1 Analytics — interactive Dash dashboard.

Run with:
    python app.py
then open http://127.0.0.1:8050
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, dash_table

import data as d
import theme as th

app = Dash(__name__, title="F1 Analytics", update_title=None, suppress_callback_exceptions=True)
server = app.server  # exposed for WSGI deployment if ever needed

SEASON_MARKS = {y: str(y) for y in range(d.MIN_SEASON, d.MAX_SEASON + 1, 10)}
SEASON_MARKS[d.MAX_SEASON] = str(d.MAX_SEASON)

DEFAULT_DRIVERS = ["hamilton", "max_verstappen", "michael_schumacher"]
DEFAULT_CONSTRUCTORS = ["Ferrari", "Mercedes", "Red Bull", "McLaren"]
DEFAULT_CIRCUIT = "monza"


# ================================================================== #
# Layout building blocks
# ================================================================== #
def kpi_card(kpi_id, label):
    return html.Div(
        [html.Div(id=kpi_id, className="kpi-value"), html.Div(label, className="kpi-label")],
        className="kpi-card",
    )


def chart_card(title, graph_id, note=None, height=None):
    """Card wrapping a dcc.Graph, with a dedicated slot below it for a
    data-driven insight sentence (filled by the same callback that draws
    the figure)."""
    children = [html.Div(title, className="chart-card-title")]
    if note:
        children.append(html.Div(note, className="chart-card-note"))
    children.append(dcc.Graph(id=graph_id, config={"displayModeBar": False},
                               style={"height": f"{height}px"} if height else {}))
    children.append(html.Div(id=f"{graph_id}-insight"))
    return html.Div(children, className="chart-card")


def table_card(title, table_id, note=None):
    """Card wrapping a DataTable that gets filled in (table + insight
    sentence together) by its callback. No dangling graph placeholder here
    - a previous version reused chart_card() for tables, which silently
    dropped the table div because an empty html.Div() is falsy in Python."""
    children = [html.Div(title, className="chart-card-title")]
    if note:
        children.append(html.Div(note, className="chart-card-note"))
    children.append(html.Div(id=table_id))
    return html.Div(children, className="chart-card")


def insight(text, muted=False):
    cls = "chart-insight chart-insight-muted" if muted else "chart-insight"
    return html.Div(text, className=cls)


def season_range_slider():
    return html.Div(
        [
            html.Span("Período (temporadas)", className="filter-label"),
            dcc.RangeSlider(
                id="season-range", min=d.MIN_SEASON, max=d.MAX_SEASON,
                value=[d.MIN_SEASON, d.MAX_SEASON], marks=SEASON_MARKS,
                step=1, allowCross=False, tooltip={"placement": "bottom", "always_visible": False},
            ),
        ],
        className="filter-bar",
    )


def header():
    return html.Div(
        [
            html.Div(
                [
                    html.H1(["F1 ", html.Span("ANALYTICS")], className="app-title"),
                    html.Div("75 anos de Fórmula 1 em dados — 1950 a 2024", className="app-subtitle"),
                ]
            ),
            html.Div(
                [
                    html.Div(f"{d.MIN_SEASON}\u2013{d.MAX_SEASON}"),
                    html.Div("1.125 CORRIDAS · 861 PILOTOS · 174 EQUIPES"),
                ],
                className="app-meta",
            ),
        ],
        className="app-header",
    )


def kpi_row():
    return html.Div(
        [
            kpi_card("kpi-races", "Corridas"),
            kpi_card("kpi-drivers", "Pilotos"),
            kpi_card("kpi-constructors", "Equipes"),
            kpi_card("kpi-countries", "Países-sede"),
            kpi_card("kpi-dnf", "Taxa de DNF"),
            kpi_card("kpi-topwinner", "Mais vitórias no período"),
        ],
        className="kpi-row",
    )


# ================================================================== #
# Tab layouts
# ================================================================== #
def tab_overview():
    return html.Div([
        html.Div([
            chart_card(
                "Crescimento do calendário e do grid",
                "ov-growth", note="Corridas e nº de pilotos distintos por temporada",
            ),
            chart_card(
                "Domínio por equipe",
                "ov-dominance", note="Pontos por temporada — 8 equipes mais vitoriosas do período selecionado",
            ),
        ], className="row-2col"),
        table_card(
            "Campeões por temporada", "ov-champions-table",
            note="Lista verificada contra fonte externa — não é derivada de soma de pontos (ver README)",
        ),
    ])


def tab_drivers():
    return html.Div([
        html.Div([
            html.Span("Pilotos (comparar até 6)", className="filter-label"),
            dcc.Dropdown(
                id="driver-select", options=d.DRIVER_OPTIONS, value=DEFAULT_DRIVERS,
                multi=True, className="dash-dropdown", placeholder="Escolha pilotos...",
            ),
        ], className="filter-bar"),
        html.Div([
            chart_card("Evolução de pontos por temporada", "dr-points-evolution",
                       note="Pontos somados (corrida + sprint) por temporada de carreira"),
            chart_card("Vitórias por temporada", "dr-wins-by-season"),
        ], className="row-2col"),
        html.Div([
            chart_card("Top 15 por vitórias (no período selecionado)", "dr-top-wins"),
            chart_card("Top 15 por pole positions (no período selecionado)", "dr-top-poles"),
        ], className="row-2col"),
        table_card(
            "Estatísticas de carreira dos pilotos selecionados", "dr-stats-table",
            note="Considera apenas o período selecionado no filtro global",
        ),
    ])


def tab_constructors():
    return html.Div([
        html.Div([
            html.Span("Equipes (comparar até 6)", className="filter-label"),
            dcc.Dropdown(
                id="constructor-select", options=d.CONSTRUCTOR_OPTIONS, value=DEFAULT_CONSTRUCTORS,
                multi=True, className="dash-dropdown", placeholder="Escolha equipes...",
            ),
        ], className="filter-bar"),
        chart_card("Pontos por temporada", "co-points-evolution",
                   note="Equipes selecionadas, no período do filtro global"),
        html.Div([
            chart_card("Top 12 equipes por vitórias", "co-top-wins"),
            chart_card("Top 12 equipes por títulos de construtores", "co-top-titles"),
        ], className="row-2col"),
        table_card(
            "Estatísticas de carreira das equipes selecionadas", "co-stats-table",
            note="Considera apenas o período selecionado no filtro global",
        ),
    ])


def tab_races():
    return html.Div([
        html.Div([
            chart_card("Largada x posição final", "ra-grid-vs-finish",
                       note="Densidade de resultados — quanto mais perto da diagonal, mais a largada decidiu"),
            chart_card("Taxa de DNF por década", "ra-dnf-rate"),
        ], className="row-2col"),
        html.Div([
            chart_card("Causas de não-classificação", "ra-dnf-causes"),
            chart_card("Duração mediana de pit stop por temporada", "ra-pitstop-trend",
                       note="Tempo total no pit lane, entrada a saída — dados disponíveis desde 2011"),
        ], className="row-2col"),
        html.Div([
            html.Span("Circuito para evolução de ritmo de classificação", className="filter-label"),
            dcc.Dropdown(id="race-circuit-select", options=d.CIRCUIT_OPTIONS, value=DEFAULT_CIRCUIT,
                        className="dash-dropdown", clearable=False),
        ], className="filter-bar"),
        chart_card("Evolução do tempo de volta na classificação", "ra-quali-pace",
                   note="Melhor tempo de classificação por temporada no circuito selecionado (dados desde 1994)"),
    ])


def tab_circuits():
    return html.Div([
        chart_card("Mapa de circuitos", "ci-map", height=460,
                   note="Tamanho do ponto = número de corridas sediadas no período selecionado"),
        html.Div([
            chart_card("Circuitos com mais corridas", "ci-top-circuits"),
            chart_card("Países que mais sediaram corridas", "ci-top-countries"),
        ], className="row-2col"),
        table_card("Estatísticas por circuito", "ci-stats-table"),
    ])


# ================================================================== #
# App layout
# ================================================================== #
app.layout = html.Div(
    [
        html.Div(
            [
                header(),
                kpi_row(),
                season_range_slider(),
                dcc.Tabs(
                    id="tabs", value="overview", className="dash-tabs",
                    children=[
                        dcc.Tab(label="Visão Geral", value="overview"),
                        dcc.Tab(label="Pilotos", value="drivers"),
                        dcc.Tab(label="Construtores", value="constructors"),
                        dcc.Tab(label="Corridas & Quali", value="races"),
                        dcc.Tab(label="Circuitos", value="circuits"),
                    ],
                ),
                html.Div(id="tab-content", style={"marginTop": "18px"}),
                html.Div(
                    "F1 Analytics · dataset 1950-2024 (schema Ergast) · construído com Python, pandas e Dash",
                    className="app-footer",
                ),
            ],
            className="app-shell",
        )
    ]
)


# ================================================================== #
# Tab switch
# ================================================================== #
@app.callback(Output("tab-content", "children"), Input("tabs", "value"))
def render_tab(tab):
    return {
        "overview": tab_overview,
        "drivers": tab_drivers,
        "constructors": tab_constructors,
        "races": tab_races,
        "circuits": tab_circuits,
    }[tab]()


# ================================================================== #
# KPI row (reacts to the global season filter)
# ================================================================== #
@app.callback(
    Output("kpi-races", "children"), Output("kpi-drivers", "children"),
    Output("kpi-constructors", "children"), Output("kpi-countries", "children"),
    Output("kpi-dnf", "children"), Output("kpi-topwinner", "children"),
    Input("season-range", "value"),
)
def update_kpis(season_range):
    fr = d.season_filtered(d.fact_results, season_range)
    races = fr["raceId"].nunique()
    drivers = fr["driverId"].nunique()
    constructors = fr["constructor_family"].nunique()
    countries = fr["circuitCountry"].nunique()
    dnf_rate = (~fr["classified"]).mean() * 100
    top = fr.groupby("driverFullName")["is_win"].sum().sort_values(ascending=False)
    top_txt = f"{top.index[0]} ({int(top.iloc[0])})" if len(top) else "\u2014"
    return f"{races:,}", f"{drivers:,}", f"{constructors:,}", f"{countries:,}", f"{dnf_rate:.1f}%", top_txt


# ================================================================== #
# Overview tab callbacks
# ================================================================== #
@app.callback(Output("ov-growth", "figure"), Output("ov-growth-insight", "children"),
              Input("season-range", "value"))
def ov_growth(season_range):
    fr = d.season_filtered(d.fact_results, season_range)
    g = fr.groupby("season").agg(races=("raceId", "nunique"), drivers=("driverId", "nunique")).reset_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=g["season"], y=g["races"], name="Corridas", line=dict(color=th.PURPLE, width=2)))
    fig.add_trace(go.Scatter(x=g["season"], y=g["drivers"], name="Pilotos", line=dict(color=th.GREEN, width=2),
                              yaxis="y2"))
    fig.update_layout(yaxis=dict(title="Corridas"), yaxis2=dict(title="Pilotos", overlaying="y", side="right",
                                                                  showgrid=False))
    first, last = g.iloc[0], g.iloc[-1]
    txt = (f"De {int(first['season'])} a {int(last['season'])}: corridas por temporada foram de "
           f"{int(first['races'])} para {int(last['races'])}; pilotos distintos, de "
           f"{int(first['drivers'])} para {int(last['drivers'])}.")
    return th.style_fig(fig), insight(txt)


@app.callback(Output("ov-dominance", "figure"), Output("ov-dominance-insight", "children"),
              Input("season-range", "value"))
def ov_dominance(season_range):
    cs = d.season_filtered(d.agg_constructor_season, season_range)
    totals = cs.groupby("constructor_family")["points"].sum().sort_values(ascending=False)
    top_teams = totals.head(8).index.tolist()
    sub = cs[cs["constructor_family"].isin(top_teams)]
    fig = go.Figure()
    for i, team in enumerate(top_teams):
        t = sub[sub["constructor_family"] == team].sort_values("season")
        fig.add_trace(go.Scatter(x=t["season"], y=t["points"], name=team, stackgroup="one",
                                  line=dict(width=0.5, color=th.CATEGORICAL[i % len(th.CATEGORICAL)])))
    fig.update_layout(yaxis_title="Pontos na temporada")
    txt = (f"{totals.index[0]} foi a equipe com mais pontos somados no período selecionado: "
           f"{totals.iloc[0]:,.0f} pts (à frente de {totals.index[1]}, com {totals.iloc[1]:,.0f}).")
    return th.style_fig(fig), insight(txt)


@app.callback(Output("ov-champions-table", "children"), Input("season-range", "value"))
def ov_champions_table(season_range):
    sc = d.season_filtered(d.season_champions, season_range).sort_values("season", ascending=False)
    n_seasons = len(sc)
    if n_seasons == 0:
        return insight("Nenhuma temporada no período selecionado.", muted=True)
    most_common = sc["champion_driver_name"].value_counts()
    txt = (f"{n_seasons} temporada(s) no período, com {sc['champion_driver_name'].nunique()} "
           f"piloto(s) campeão(s) diferente(s). Mais títulos no período: {most_common.index[0]} "
           f"({int(most_common.iloc[0])}x).")
    tbl = sc.rename(columns={
        "season": "Temporada", "champion_driver_name": "Campeão (Pilotos)",
        "champion_constructor_family": "Campeã (Construtores)",
    })[["Temporada", "Campeão (Pilotos)", "Campeã (Construtores)"]]
    tbl["Campeã (Construtores)"] = tbl["Campeã (Construtores)"].fillna("\u2014 (título ainda não existia)")
    return html.Div([insight(txt), styled_table(tbl, page_size=10)])


# ================================================================== #
# Drivers tab callbacks
# ================================================================== #
@app.callback(Output("dr-points-evolution", "figure"), Output("dr-points-evolution-insight", "children"),
              Input("driver-select", "value"), Input("season-range", "value"))
def dr_points_evolution(driver_ids, season_range):
    if not driver_ids:
        return th.empty_state_fig("Escolha ao menos um piloto"), insight("Escolha ao menos um piloto acima.", muted=True)
    dsp = d.season_filtered(d.driver_standings_progression, season_range)
    dsp = dsp[dsp["driverId"].isin(driver_ids)]
    season_totals = dsp.groupby(["season", "driverId", "driverFullName"])["points_cum"].max().reset_index()
    if season_totals.empty:
        return th.empty_state_fig("Sem dados no período"), insight("Sem dados no período selecionado.", muted=True)
    fig = px.line(season_totals, x="season", y="points_cum", color="driverFullName", markers=True)
    fig.update_layout(yaxis_title="Pontos acumulados na temporada", xaxis_title=None, legend_title=None)
    best = season_totals.loc[season_totals["points_cum"].idxmax()]
    txt = (f"Melhor temporada entre os selecionados: {best['driverFullName']} em {int(best['season'])}, "
           f"com {best['points_cum']:.0f} pontos acumulados.")
    return th.style_fig(fig), insight(txt)


@app.callback(Output("dr-wins-by-season", "figure"), Output("dr-wins-by-season-insight", "children"),
              Input("driver-select", "value"), Input("season-range", "value"))
def dr_wins_by_season(driver_ids, season_range):
    if not driver_ids:
        return th.empty_state_fig("Escolha ao menos um piloto"), insight("Escolha ao menos um piloto acima.", muted=True)
    fr = d.season_filtered(d.fact_results, season_range)
    fr = fr[fr["driverId"].isin(driver_ids)]
    g = fr.groupby(["season", "driverFullName"])["is_win"].sum().reset_index()
    g = g[g["is_win"] > 0]
    if g.empty:
        return th.empty_state_fig("Nenhuma vitória no período"), insight("Nenhum dos selecionados venceu corridas no período.", muted=True)
    fig = px.bar(g, x="season", y="is_win", color="driverFullName", barmode="stack")
    fig.update_layout(yaxis_title="Vitórias", xaxis_title=None, legend_title=None)
    totals = g.groupby("driverFullName")["is_win"].sum().sort_values(ascending=False)
    txt = f"No período, {totals.index[0]} tem mais vitórias entre os selecionados: {int(totals.iloc[0])}."
    return th.style_fig(fig), insight(txt)


@app.callback(Output("dr-top-wins", "figure"), Output("dr-top-wins-insight", "children"),
              Input("season-range", "value"))
def dr_top_wins(season_range):
    fr = d.season_filtered(d.fact_results, season_range)
    g = fr.groupby("driverFullName")["is_win"].sum().sort_values(ascending=False).head(15).iloc[::-1]
    fig = go.Figure(go.Bar(x=g.values, y=g.index, orientation="h", marker_color=th.PURPLE))
    fig.update_layout(xaxis_title="Vitórias")
    txt = f"{g.index[-1]} lidera com {int(g.iloc[-1])} vitórias no período selecionado."
    return th.style_fig(fig, legend=False, height=440), insight(txt)


@app.callback(Output("dr-top-poles", "figure"), Output("dr-top-poles-insight", "children"),
              Input("season-range", "value"))
def dr_top_poles(season_range):
    fq = d.season_filtered(d.fact_qualifying, season_range)
    poles = fq[fq["position"] == 1]
    g = poles.groupby("driverName").size().sort_values(ascending=False).head(15).iloc[::-1]
    if g.empty:
        return th.empty_state_fig("Sem dados de pole no período"), insight("Sem dados de qualificação no período (dados desde 1994).", muted=True)
    fig = go.Figure(go.Bar(x=g.values, y=g.index, orientation="h", marker_color=th.GREEN))
    fig.update_layout(xaxis_title="Pole positions")
    txt = f"{g.index[-1]} lidera com {int(g.iloc[-1])} pole positions no período (dados de quali desde 1994)."
    return th.style_fig(fig, legend=False, height=440), insight(txt)


@app.callback(Output("dr-stats-table", "children"),
              Input("driver-select", "value"), Input("season-range", "value"))
def dr_stats_table(driver_ids, season_range):
    if not driver_ids:
        return insight("Escolha ao menos um piloto acima para ver as estatísticas.", muted=True)
    fr = d.season_filtered(d.fact_results, season_range)
    fr = fr[fr["driverId"].isin(driver_ids)]
    if fr.empty:
        return insight("Nenhum dos pilotos selecionados correu no período escolhido.", muted=True)
    g = fr.groupby("driverFullName").agg(
        Corridas=("raceId", "nunique"), Vitórias=("is_win", "sum"), Pódios=("is_podium", "sum"),
        Pontos=("total_points", "sum"), DNFs=("classified", lambda s: int((~s).sum())),
    ).reset_index().rename(columns={"driverFullName": "Piloto"})
    poles = d.season_filtered(d.fact_qualifying, season_range)
    poles = poles[(poles["position"] == 1) & (poles["driverName"].isin(g["Piloto"]))]
    pole_counts = poles.groupby("driverName").size().rename("Poles")
    g = g.merge(pole_counts, left_on="Piloto", right_index=True, how="left")
    g["Poles"] = g["Poles"].fillna(0).astype(int)
    g = g.sort_values("Pontos", ascending=False)
    leader = g.iloc[0]
    txt = (f"{leader['Piloto']} lidera o grupo selecionado no período: {int(leader['Pontos'])} pts, "
           f"{int(leader['Vitórias'])} vitórias, {int(leader['Pódios'])} pódios.")
    return html.Div([insight(txt), styled_table(g)])


# ================================================================== #
# Constructors tab callbacks
# ================================================================== #
@app.callback(Output("co-points-evolution", "figure"), Output("co-points-evolution-insight", "children"),
              Input("constructor-select", "value"), Input("season-range", "value"))
def co_points_evolution(teams, season_range):
    if not teams:
        return th.empty_state_fig("Escolha ao menos uma equipe"), insight("Escolha ao menos uma equipe acima.", muted=True)
    cp = d.season_filtered(d.constructor_standings_progression, season_range)
    cp = cp[cp["constructor_family"].isin(teams)]
    season_totals = cp.groupby(["season", "constructor_family"])["points_cum"].max().reset_index()
    if season_totals.empty:
        return th.empty_state_fig("Sem dados no período"), insight("Sem dados no período selecionado.", muted=True)
    fig = px.line(season_totals, x="season", y="points_cum", color="constructor_family", markers=True)
    fig.update_layout(yaxis_title="Pontos acumulados na temporada", xaxis_title=None, legend_title=None)
    best = season_totals.loc[season_totals["points_cum"].idxmax()]
    txt = (f"Melhor temporada entre as selecionadas: {best['constructor_family']} em {int(best['season'])}, "
           f"com {best['points_cum']:.0f} pontos acumulados.")
    return th.style_fig(fig), insight(txt)


@app.callback(Output("co-top-wins", "figure"), Output("co-top-wins-insight", "children"),
              Input("season-range", "value"))
def co_top_wins(season_range):
    fr = d.season_filtered(d.fact_results, season_range)
    g = fr.groupby("constructor_family")["is_win"].sum().sort_values(ascending=False).head(12).iloc[::-1]
    fig = go.Figure(go.Bar(x=g.values, y=g.index, orientation="h", marker_color=th.PURPLE))
    fig.update_layout(xaxis_title="Vitórias")
    txt = f"{g.index[-1]} lidera com {int(g.iloc[-1])} vitórias no período selecionado."
    return th.style_fig(fig, legend=False, height=400), insight(txt)


@app.callback(Output("co-top-titles", "figure"), Output("co-top-titles-insight", "children"),
              Input("season-range", "value"))
def co_top_titles(season_range):
    sc = d.season_filtered(d.season_champions, season_range).dropna(subset=["champion_constructor_family"])
    g = sc["champion_constructor_family"].value_counts().head(12).iloc[::-1]
    if g.empty:
        return th.empty_state_fig("Sem títulos de construtores no período"), \
               insight("O título de construtores só existe a partir de 1958.", muted=True)
    fig = go.Figure(go.Bar(x=g.values, y=g.index, orientation="h", marker_color=th.GREEN))
    fig.update_layout(xaxis_title="Títulos de construtores")
    txt = f"{g.index[-1]} lidera com {int(g.iloc[-1])} título(s) de construtores no período."
    return th.style_fig(fig, legend=False, height=400), insight(txt)


@app.callback(Output("co-stats-table", "children"),
              Input("constructor-select", "value"), Input("season-range", "value"))
def co_stats_table(teams, season_range):
    if not teams:
        return insight("Escolha ao menos uma equipe acima para ver as estatísticas.", muted=True)
    fr = d.season_filtered(d.fact_results, season_range)
    fr = fr[fr["constructor_family"].isin(teams)]
    if fr.empty:
        return insight("Nenhuma das equipes selecionadas correu no período escolhido.", muted=True)
    sc = d.season_filtered(d.season_champions, season_range).dropna(subset=["champion_constructor_family"])
    titles = sc["champion_constructor_family"].value_counts()
    g = fr.groupby("constructor_family").agg(
        Corridas=("raceId", "nunique"), Vitórias=("is_win", "sum"), Pódios=("is_podium", "sum"),
        Pontos=("total_points", "sum"),
    ).reset_index().rename(columns={"constructor_family": "Equipe"})
    g["Títulos (no período)"] = g["Equipe"].map(titles).fillna(0).astype(int)
    g = g.sort_values("Pontos", ascending=False)
    leader = g.iloc[0]
    txt = (f"{leader['Equipe']} lidera o grupo selecionado no período: {int(leader['Pontos'])} pts, "
           f"{int(leader['Vitórias'])} vitórias, {int(leader['Títulos (no período)'])} título(s).")
    return html.Div([insight(txt), styled_table(g)])


# ================================================================== #
# Races & Quali tab callbacks
# ================================================================== #
@app.callback(Output("ra-grid-vs-finish", "figure"), Output("ra-grid-vs-finish-insight", "children"),
              Input("season-range", "value"))
def ra_grid_vs_finish(season_range):
    fr = d.season_filtered(d.fact_results, season_range)
    sample = fr[(fr["grid"] > 0) & (fr["position"] > 0)]
    corr = sample[["grid", "position"]].corr().iloc[0, 1] if len(sample) > 1 else float("nan")
    plot_sample = sample.sample(15000, random_state=42) if len(sample) > 15000 else sample
    fig = go.Figure(go.Histogram2d(
        x=plot_sample["grid"], y=plot_sample["position"], colorscale="Purples", nbinsx=24, nbinsy=24,
        colorbar=dict(title="corridas", tickfont=dict(color=th.MUTED)),
    ))
    fig.add_trace(go.Scatter(x=[0, 24], y=[0, 24], mode="lines",
                              line=dict(color=th.GREEN, dash="dash", width=1.5), name="largada = chegada"))
    fig.update_layout(xaxis_title="Grid (largada)", yaxis_title="Posição final")
    pole_win_rate = (sample[sample["grid"] == 1]["position"] == 1).mean() * 100 if (sample["grid"] == 1).any() else float("nan")
    txt = (f"Correlação largada-chegada de {corr:.2f} no período. Quem larga em 1º vence a corrida "
           f"{pole_win_rate:.0f}% das vezes.")
    return th.style_fig(fig, legend=False), insight(txt)


@app.callback(Output("ra-dnf-rate", "figure"), Output("ra-dnf-rate-insight", "children"),
              Input("season-range", "value"))
def ra_dnf_rate(season_range):
    fr = d.season_filtered(d.fact_results, season_range)
    dnf = fr.groupby("decade").apply(lambda x: (~x["classified"]).mean() * 100, include_groups=False)
    fig = go.Figure(go.Scatter(x=dnf.index, y=dnf.values, mode="lines+markers",
                                line=dict(color=th.RED, width=2.5)))
    fig.update_layout(yaxis_title="% não-classificados", xaxis_title=None)
    if len(dnf) >= 2:
        txt = (f"Taxa de DNF foi de {dnf.iloc[0]:.0f}% na década de {int(dnf.index[0])} para "
               f"{dnf.iloc[-1]:.0f}% na década de {int(dnf.index[-1])}.")
    else:
        txt = f"Taxa de DNF na década de {int(dnf.index[0])}: {dnf.iloc[0]:.0f}%."
    return th.style_fig(fig, legend=False), insight(txt)


@app.callback(Output("ra-dnf-causes", "figure"), Output("ra-dnf-causes-insight", "children"),
              Input("season-range", "value"))
def ra_dnf_causes(season_range):
    fr = d.season_filtered(d.fact_results, season_range)
    causes = fr[~fr["classified"]]["status_category"].value_counts()
    fig = go.Figure(go.Pie(labels=causes.index, values=causes.values, hole=0.45,
                            marker=dict(colors=th.CATEGORICAL, line=dict(color=th.PANEL, width=2))))
    pct = causes.iloc[0] / causes.sum() * 100
    txt = f"{causes.index[0]} é a causa mais comum de não-classificação no período: {pct:.0f}% dos casos."
    return th.style_fig(fig, legend=True), insight(txt)


@app.callback(Output("ra-pitstop-trend", "figure"), Output("ra-pitstop-trend-insight", "children"),
              Input("season-range", "value"))
def ra_pitstop_trend(season_range):
    ps = d.season_filtered(d.fact_pitstops, season_range)
    if ps.empty:
        return th.empty_state_fig("Sem dados de pit stop antes de 2011"), \
               insight("Sem dados de pit stop disponíveis antes de 2011.", muted=True)
    trend = ps.groupby("season")["duration_sec"].median().reset_index()
    fig = go.Figure(go.Scatter(x=trend["season"], y=trend["duration_sec"], mode="lines+markers",
                                line=dict(color=th.GREEN, width=2.5)))
    fig.update_layout(yaxis_title="Segundos (mediana)", xaxis_title=None)
    delta = trend["duration_sec"].iloc[-1] - trend["duration_sec"].iloc[0]
    direction = "praticamente estável" if abs(delta) < 1 else ("caiu" if delta < 0 else "subiu")
    txt = (f"Mediana {direction} de {trend['duration_sec'].iloc[0]:.1f}s ({int(trend['season'].iloc[0])}) para "
           f"{trend['duration_sec'].iloc[-1]:.1f}s ({int(trend['season'].iloc[-1])}) — lembrando que essa métrica "
           "é o tempo total no pit lane, não só a troca de pneu.")
    return th.style_fig(fig, legend=False), insight(txt)


@app.callback(Output("ra-quali-pace", "figure"), Output("ra-quali-pace-insight", "children"),
              Input("race-circuit-select", "value"), Input("season-range", "value"))
def ra_quali_pace(circuit_id, season_range):
    if not circuit_id:
        return th.empty_state_fig("Escolha um circuito"), insight("Escolha um circuito acima.", muted=True)
    circuit_name = d.dim_circuits.loc[d.dim_circuits["circuitId"] == circuit_id, "circuitName"].iloc[0]
    race_ids = d.dim_races.loc[d.dim_races["circuitId"] == circuit_id, "raceId"]
    fq = d.season_filtered(d.fact_qualifying[d.fact_qualifying["raceId"].isin(race_ids)], season_range)
    best = fq.groupby("season")["best_time_sec"].min().dropna().reset_index()
    if best.empty:
        return th.empty_state_fig("Sem dados de tempo de classificação para este circuito/período (dados desde 1994)"), \
               insight("Sem dados de tempo de classificação para este circuito/período (dados desde 1994).", muted=True)
    fig = go.Figure(go.Scatter(x=best["season"], y=best["best_time_sec"], mode="lines+markers",
                                line=dict(color=th.PURPLE, width=2)))
    fig.update_layout(yaxis_title="Melhor tempo de quali (s)", xaxis_title=None)
    fastest_row = best.loc[best["best_time_sec"].idxmin()]
    txt = (f"Volta mais rápida de classificação em {circuit_name} no período: {fastest_row['best_time_sec']:.2f}s, "
           f"em {int(fastest_row['season'])}.")
    return th.style_fig(fig, legend=False), insight(txt)


# ================================================================== #
# Circuits tab callbacks
# ================================================================== #
@app.callback(Output("ci-map", "figure"), Output("ci-map-insight", "children"), Input("season-range", "value"))
def ci_map(season_range):
    races_in_range = d.dim_races[d.dim_races["season"].between(season_range[0], season_range[1])]
    counts = races_in_range.groupby("circuitId")["raceId"].nunique().rename("races")
    circ = d.dim_circuits.merge(counts, on="circuitId", how="inner")
    fig = go.Figure(go.Scattergeo(
        lon=circ["long"], lat=circ["lat"], text=circ["circuitName"] + " (" + circ["races"].astype(str) + " corridas)",
        mode="markers",
        marker=dict(size=(circ["races"] ** 0.5) * 4 + 4, color=th.PURPLE, line=dict(width=1, color=th.TEXT), opacity=0.85),
    ))
    fig.update_geos(bgcolor=th.PANEL, showland=True, landcolor=th.PANEL_2, showocean=True,
                     oceancolor=th.BG, showcountries=True, countrycolor=th.BORDER,
                     coastlinecolor=th.BORDER, framecolor=th.BORDER)
    fig.update_layout(paper_bgcolor=th.PANEL, margin=dict(l=0, r=0, t=10, b=0))
    n_countries = races_in_range["circuitCountry"].nunique()
    txt = f"{len(circ)} circuitos diferentes sediaram corridas em {n_countries} países no período selecionado."
    return fig, insight(txt)


@app.callback(Output("ci-top-circuits", "figure"), Output("ci-top-circuits-insight", "children"),
              Input("season-range", "value"))
def ci_top_circuits(season_range):
    races_in_range = d.dim_races[d.dim_races["season"].between(season_range[0], season_range[1])]
    g = races_in_range.groupby("circuitName")["raceId"].nunique().sort_values(ascending=False).head(12).iloc[::-1]
    fig = go.Figure(go.Bar(x=g.values, y=g.index, orientation="h", marker_color=th.PURPLE))
    fig.update_layout(xaxis_title="Corridas sediadas")
    txt = f"{g.index[-1]} sediou mais corridas que qualquer outro circuito no período: {int(g.iloc[-1])}."
    return th.style_fig(fig, legend=False, height=400), insight(txt)


@app.callback(Output("ci-top-countries", "figure"), Output("ci-top-countries-insight", "children"),
              Input("season-range", "value"))
def ci_top_countries(season_range):
    races_in_range = d.dim_races[d.dim_races["season"].between(season_range[0], season_range[1])]
    g = races_in_range.groupby("circuitCountry")["raceId"].nunique().sort_values(ascending=False).head(12).iloc[::-1]
    fig = go.Figure(go.Bar(x=g.values, y=g.index, orientation="h", marker_color=th.AMBER))
    fig.update_layout(xaxis_title="Corridas")
    txt = f"{g.index[-1]} sediou mais corridas que qualquer outro país no período: {int(g.iloc[-1])}."
    return th.style_fig(fig, legend=False, height=400), insight(txt)


@app.callback(Output("ci-stats-table", "children"), Input("season-range", "value"))
def ci_stats_table(season_range):
    races_in_range = d.dim_races[d.dim_races["season"].between(season_range[0], season_range[1])]
    ids = races_in_range["raceId"]
    fr = d.fact_results[d.fact_results["raceId"].isin(ids)]
    g = races_in_range.groupby(["circuitId", "circuitName", "circuitCountry"])["raceId"].nunique().reset_index()
    g = g.rename(columns={"raceId": "Corridas", "circuitName": "Circuito", "circuitCountry": "País"})
    finishers = fr.merge(races_in_range[["raceId", "circuitId"]], on="raceId", how="left") \
        .groupby("circuitId")["classified"].mean().rename("% de carros que terminam") * 100
    g = g.merge(finishers, on="circuitId", how="left").drop(columns=["circuitId"])
    g["% de carros que terminam"] = g["% de carros que terminam"].round(1)
    g = g.sort_values("Corridas", ascending=False)
    if g.empty:
        return insight("Nenhum circuito no período selecionado.", muted=True)
    most_reliable = g.sort_values("% de carros que terminam", ascending=False).iloc[0]
    txt = (f"{most_reliable['Circuito']} tem a maior taxa de carros que terminam a corrida no período: "
           f"{most_reliable['% de carros que terminam']:.0f}%.")
    return html.Div([insight(txt), styled_table(g, page_size=12)])


# ================================================================== #
# Shared table styling
# ================================================================== #
def styled_table(df, page_size=8):
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].round(1)
    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
        page_size=page_size,
        sort_action="native",
        style_header={"backgroundColor": th.PANEL_2, "color": th.MUTED, "border": f"1px solid {th.BORDER}",
                      "textTransform": "uppercase", "fontSize": "11px", "letterSpacing": "0.5px"},
        style_cell={"backgroundColor": th.PANEL, "color": th.TEXT, "border": f"1px solid {th.BORDER}",
                    "padding": "8px 10px", "textAlign": "left"},
        style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": th.PANEL_2}],
        style_table={"overflowX": "auto"},
    )


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
