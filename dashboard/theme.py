"""Shared color palette + plotly figure styling for the F1 Analytics dashboard."""

BG = "#0B0E14"
PANEL = "#12161F"
PANEL_2 = "#171C27"
BORDER = "#242A36"
TEXT = "#E8E9ED"
MUTED = "#8B92A0"

PURPLE = "#A855F7"   # fastest-lap purple (F1 timing-screen convention)
GREEN = "#00D68F"    # personal-best green
AMBER = "#F5A623"
RED = "#FF5C5C"
BLUE = "#4EA8DE"

CATEGORICAL = [PURPLE, GREEN, AMBER, BLUE, RED, "#7C83FD", "#FF8FB1", "#5EEAD4",
               "#F472B6", "#FACC15", "#38BDF8", "#C084FC"]

FONT_FAMILY = "Inter, sans-serif"
FONT_MONO = "JetBrains Mono, monospace"


def style_fig(fig, height=380, legend=True, mono_axes=False):
    """Apply the dark timing-tower theme to a plotly figure in place, return it."""
    fig.update_layout(
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(family=FONT_FAMILY, color=TEXT, size=12),
        height=height,
        margin=dict(l=50, r=20, t=30, b=40),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=MUTED),
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
        ) if legend else dict(),
        showlegend=legend,
        hoverlabel=dict(bgcolor=PANEL_2, font=dict(family=FONT_FAMILY, color=TEXT), bordercolor=BORDER),
        colorway=CATEGORICAL,
    )
    axis_font = dict(family=FONT_MONO if mono_axes else FONT_FAMILY, color=MUTED, size=11)
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=axis_font, title_font=dict(color=MUTED, size=12))
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=axis_font, title_font=dict(color=MUTED, size=12))
    return fig


def empty_state_fig(message="Sem dados para os filtros selecionados"):
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(color=MUTED, size=14))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return style_fig(fig, height=300, legend=False)
