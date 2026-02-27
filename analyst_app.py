import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_plotly

# -----------------------------------------------------------------------------
# 1. Data Loading and Cleaning
# -----------------------------------------------------------------------------
df = pd.read_csv("cleaned_dataset.csv")

df = df.replace([np.inf, -np.inf], np.nan)
df = df.dropna(subset=['Stream', 'Views', 'Likes', 'Comments', 'Artist', 'Track', 'most_playedon'])

audio_features = [
    'Danceability', 'Energy', 'Valence', 'Acousticness', 
    'Liveness', 'Speechiness', 'Tempo', 'Loudness'
]
magnitude_features = ['Stream', 'Views', 'Likes', 'Comments']

# -----------------------------------------------------------------------------
# 2. Frontend UI (Forcing 100% Width)
# -----------------------------------------------------------------------------
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h4("🔬 Analyst Filters"),
        ui.hr(),
        
        ui.input_select("x_axis", "X-Axis Feature", choices=audio_features, selected="Danceability"),
        ui.input_select("y_axis", "Y-Axis Feature", choices=audio_features, selected="Energy"),
        ui.input_select("size_axis", "Bubble Size Represents", choices=magnitude_features, selected="Likes"),
        
        ui.hr(),
        ui.input_slider("stream_filter", "Min Spotify Streams (M)", min=0, max=1000, value=10, step=10),
        ui.input_slider("views_filter", "Min YouTube Views (M)", min=0, max=1000, value=10, step=10),
        ui.input_checkbox_group("platform_filter", "Dominant Platform", choices=["Spotify", "Youtube"], selected=["Spotify", "Youtube"]),
        
        bg="#f8f9fa",
        width=320 
    ),
    
    ui.h2("🧬 Audio Features Correlation Studio"),
    
    ui.layout_columns(
        ui.value_box("Sample Tracks", ui.output_text("kpi_count"), theme="bg-dark"),
        ui.value_box("X-Axis Mean", ui.output_text("kpi_x_mean"), theme="bg-info"),
        ui.value_box("Y-Axis Mean", ui.output_text("kpi_y_mean"), theme="bg-primary"),
    ),
    
    ui.navset_card_underline(
        ui.nav_panel(
            "🎯 Bivariate Scatter", 
            output_widget("scatter_chart")
        ),
        ui.nav_panel(
            "📊 Platform Violin", 
            output_widget("violin_chart")
        ),
        ui.nav_panel(
            "📈 Feature Histograms", 
            # 【终极修复点】：强制使用 12 列（100%宽度）的布局容器包裹它们！
            ui.layout_columns(
                ui.card(output_widget("hist_x_chart"), full_screen=True),
                ui.card(output_widget("hist_y_chart"), full_screen=True),
                col_widths=[12, 12] # 第一张图占 12 列 (100%)，第二张图占 12 列 (100%)
            )
        )
    )
)

# -----------------------------------------------------------------------------
# 3. Backend Server Logic
# -----------------------------------------------------------------------------
def server(input, output, session):
    
    @reactive.Calc
    def filtered_data():
        filtered_df = df.copy()
        
        # 将原始列名改头换面，变得极具专业性
        filtered_df = filtered_df.rename(columns={"most_playedon": "Dominant Platform"})
        
        min_stream_raw = input.stream_filter() * 1_000_000
        min_views_raw = input.views_filter() * 1_000_000
        
        filtered_df = filtered_df[
            (filtered_df["Stream"] >= min_stream_raw) & 
            (filtered_df["Views"] >= min_views_raw)
        ]
        
        if input.platform_filter():
            filtered_df = filtered_df[filtered_df["Dominant Platform"].isin(input.platform_filter())]
        else:
            filtered_df = filtered_df.iloc[0:0] 
        return filtered_df

    @render.text
    def kpi_count(): return f"{len(filtered_data()):,} tracks"
    @render.text
    def kpi_x_mean(): return "N/A" if filtered_data().empty else f"{filtered_data()[input.x_axis()].mean():.3f}"
    @render.text
    def kpi_y_mean(): return "N/A" if filtered_data().empty else f"{filtered_data()[input.y_axis()].mean():.3f}"

    def get_safe_empty_fig(text="Insufficient data"):
        fig = go.Figure()
        fig.add_annotation(text=text, x=0.5, y=0.5, showarrow=False, font=dict(size=18, color="#adb5bd"))
        fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False), plot_bgcolor="white", margin=dict(t=0,b=0,l=0,r=0))
        return fig

    # --- Chart 1: Scatter Chart ---
    @render_plotly
    def scatter_chart():
        dff = filtered_data()
        if dff.empty: return get_safe_empty_fig()
        if len(dff) > 3000: dff = dff.sample(3000, random_state=42)
            
        fig = px.scatter(
            dff, x=input.x_axis(), y=input.y_axis(), 
            color="Dominant Platform",
            color_discrete_map={"Spotify": "#1DB954", "Youtube": "#FF0000"},
            size=input.size_axis(), size_max=25,
            hover_name="Track", hover_data={"Artist": True, input.size_axis(): True},
            height=700              
        )
        fig.update_traces(marker=dict(opacity=0.6, line=dict(width=0.5, color='white')))
        fig.update_layout(
            plot_bgcolor="white", 
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), 
            font=dict(size=13),
            margin=dict(t=40, b=20, l=10, r=10) 
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f1f3f5')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f1f3f5')
        return fig

    # --- Chart 2: Violin Plot ---
    @render_plotly
    def violin_chart():
        dff = filtered_data()
        if dff.empty: return get_safe_empty_fig()
        
        fig = px.violin(
            dff, y=input.x_axis(), x="Dominant Platform", 
            color="Dominant Platform",
            color_discrete_map={"Spotify": "#1DB954", "Youtube": "#FF0000"},
            box=True, points="outliers", 
            labels={input.x_axis(): f"{input.x_axis()} Distribution"},
            height=700          
        )
        fig.update_layout(
            plot_bgcolor="white", showlegend=False, font=dict(size=13),
            margin=dict(t=40, b=20, l=10, r=10)
        )
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f1f3f5')
        return fig

    # --- Chart 3: Vertical Histograms ---
    @render_plotly
    def hist_x_chart():
        dff = filtered_data()
        if dff.empty: return get_safe_empty_fig()
        
        x_col = input.x_axis()
        fig = px.histogram(
            dff, x=x_col, color="Dominant Platform",
            color_discrete_map={"Spotify": "#1DB954", "Youtube": "#FF0000"},
            barmode="overlay", opacity=0.65, nbins=60, marginal="box", 
            title=f"<b>{x_col}</b> Distribution",
            height=450 
        )
        
        fig.update_layout(
            plot_bgcolor="white", bargap=0.05,
            legend=dict(
                yanchor="top", y=0.99, 
                xanchor="right", x=0.99, 
                bgcolor="rgba(255, 255, 255, 0.8)", 
                title=""
            ),
            font=dict(size=13), 
            margin=dict(t=50, b=20, l=10, r=10)
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f1f3f5', title="")
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f1f3f5')
        return fig

    @render_plotly
    def hist_y_chart():
        dff = filtered_data()
        if dff.empty: return get_safe_empty_fig()
        
        y_col = input.y_axis()
        fig = px.histogram(
            dff, x=y_col, color="Dominant Platform",
            color_discrete_map={"Spotify": "#1DB954", "Youtube": "#FF0000"},
            barmode="overlay", opacity=0.65, nbins=60, marginal="box", 
            title=f"<b>{y_col}</b> Distribution",
            height=450 
        )
        
        fig.update_layout(
            plot_bgcolor="white", bargap=0.05,
            showlegend=False, 
            font=dict(size=13), 
            margin=dict(t=50, b=20, l=10, r=10)
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f1f3f5', title="")
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f1f3f5')
        return fig

app = App(app_ui, server)