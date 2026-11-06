"""Small, shared visual defaults for the research explorer."""
from pathlib import Path

import streamlit as st

TEAL = '#0D7466'
CHART_CONFIG = {'displayModeBar': False, 'scrollZoom': False, 'responsive': True}
PALETTES = {
    False: dict(bg='#F7F9F8', surface='#FFFFFF', field='#EDF3F0', text='#172E28', muted='#61746D',
                border='#E0E8E3', accent=TEAL, grid='#E7EEEA', land='#E8EEEA', faint='#D7EEE5'),
    True: dict(bg='#101816', surface='#18231F', field='#21302A', text='#E8F1EC', muted='#ADC0B5',
               border='#34473D', accent='#71D2B2', grid='#304239', land='#25362E', faint='#355C4B'),
}


def palette():
    return PALETTES[bool(st.session_state.get('dark_mode', False))]


def apply_style():
    st.html(Path(__file__).with_name('style.css'))
    tokens = ';'.join(f'--atlas-{key}:{value}' for key, value in palette().items())
    scheme = 'dark' if st.session_state.get('dark_mode', False) else 'light'
    table_filter = 'invert(.9) hue-rotate(180deg)' if scheme == 'dark' else 'none'
    st.html(f'<style>:root{{{tokens};color-scheme:{scheme};--atlas-table-filter:{table_filter};}}</style>')


def search_style():
    colors = palette()
    return dict(wrapper=dict(backgroundColor=colors['surface'], color=colors['text']),
                dropdown=dict(fill=colors['muted']), clear=dict(fill=colors['muted']),
                searchbox=dict(
                    control=dict(backgroundColor=colors['field'], borderColor=colors['border']),
                    singleValue=dict(color=colors['text']), input=dict(color=colors['text']),
                    placeholder=dict(color=colors['muted']),
                    menuList=dict(backgroundColor=colors['surface'], color=colors['text']),
                    option=dict(color=colors['text'], backgroundColor=colors['surface'],
                                highlightColor=colors['field'])))


def style_chart(fig, *, height=320):
    colors = palette()
    fig.update_layout(
        template='plotly_white', height=height, paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=8, r=14, t=16, b=16),
        font=dict(family='Inter, Segoe UI, sans-serif', size=12, color=colors['muted']),
        hoverlabel=dict(bgcolor=colors['surface'], font_color=colors['text'], bordercolor=colors['border']),
        title=dict(text=''), showlegend=False,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, title=None, automargin=True)
    fig.update_yaxes(gridcolor=colors['grid'], zeroline=False, title=None, automargin=True)
    return fig


def ranking_chart(fig, count):
    style_chart(fig, height=max(290, count * 27 + 50))
    fig.update_traces(marker_color=palette()['accent'], marker_line_width=0,
                      hovertemplate='%{y}<br>%{x:,} keyword mentions<extra></extra>')
    fig.update_layout(bargap=0.38, yaxis=dict(autorange='reversed'))
    fig.update_xaxes(showgrid=True, gridcolor=palette()['grid'])
    fig.update_yaxes(showgrid=False)
    return fig
