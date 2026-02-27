import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_plotly
import textwrap

# -----------------------------------------------------------------------------
# 1. Data Loading and Cleaning
# -----------------------------------------------------------------------------
df = pd.read_csv("cleaned_dataset.csv")

df = df.replace([np.inf, -np.inf], np.nan)
df = df.dropna(subset=['Stream', 'Views', 'Likes', 'Comments', 'Artist', 'Track', 'most_playedon', 'Energy'])

album_types = ["All"] + sorted(df["Album_type"].unique().tolist())
platforms = ["All", "Spotify", "Youtube"]
magnitude_features = ['Stream', 'Views', 'Likes', 'Comments']

# -----------------------------------------------------------------------------
# 2. Frontend UI (Dual Track Dashboard)
# -----------------------------------------------------------------------------
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h4("🎛️ Executive Filters"),
        ui.hr(),
        
        ui.input_select("type_filter", "💿 Album Type", choices=album_types, selected="All"),
        ui.input_select("platform_filter", "🌐 Main Platform", choices=platforms, selected="All"),
        
        ui.input_slider("dance_filter", "💃 Danceability Index", min=0.0, max=1.0, value=[0.4, 1.0], step=0.05),
        ui.input_slider("energy_filter", "⚡ Energy Index", min=0.0, max=1.0, value=[0.0, 1.0], step=0.05),
        
        ui.hr(),
        ui.p("📊 Performance Filters"),
        ui.input_slider("stream_filter", "🟢 Min Spotify Streams (M)", min=0, max=3000, value=10, step=50),
        ui.input_slider("views_filter", "🔴 Min YouTube Views (M)", min=0, max=8000, value=10, step=100),
        
        ui.hr(),
        ui.input_select("size_axis", "⚪ Bubble Size Represents", choices=magnitude_features, selected="Likes"),
        
        bg="#f8f9fa",
        width=320
    ),
    
    ui.h2("🎧 Executive Music Performance Dashboard"),
    
    ui.layout_columns(
        ui.value_box("Total Spotify Streams", ui.output_text("kpi_streams"), theme="bg-success"),
        ui.value_box("Total YouTube Views", ui.output_text("kpi_views"), theme="bg-danger"),
        ui.value_box("Total YouTube Likes", ui.output_text("kpi_likes"), theme="bg-primary"),
    ),
    
    # two main tabs for Spotify and YouTube analysis
    ui.navset_card_underline(
        # --- 1：Spotify ---
        ui.nav_panel(
            "🟢 Top by Spotify Streams", 
            ui.layout_columns(
                ui.card(
                    ui.card_header("👑 Top 10 by Spotify Streams"),
                    output_widget("spotify_bar_chart")
                ),
                ui.card(
                    ui.card_header("🧬 Acoustic Fingerprint (Top 10 Avg)"),
                    output_widget("spotify_fingerprint_chart")
                ),
                col_widths=[7, 5] 
            )
        ),
        # --- 2：YouTube ---
        ui.nav_panel(
            "🔴 Top by YouTube Views", 
            ui.layout_columns(
                ui.card(
                    ui.card_header("👑 Top 10 by YouTube Views"),
                    output_widget("youtube_bar_chart")
                ),
                ui.card(
                    ui.card_header("🧬 Acoustic Fingerprint (Top 10 Avg)"),
                    output_widget("youtube_fingerprint_chart")
                ),
                col_widths=[7, 5] 
            )
        )
    ),
    
    # SCATTER CHART AT THE BOTTOM
    ui.card(
        ui.card_header("🚀 Platform Engagement: YouTube Views vs. Spotify Streams (Log Scale)"),
        output_widget("scatter_chart"), 
        full_screen=True
    )
)

# -----------------------------------------------------------------------------
# 3. Backend Server Logic
# -----------------------------------------------------------------------------
def server(input, output, session):
    
    @reactive.Calc
    def filtered_data():
        filtered_df = df.copy()
        
        if input.type_filter() != "All":
            filtered_df = filtered_df[filtered_df["Album_type"] == input.type_filter()]
        if input.platform_filter() != "All":
            filtered_df = filtered_df[filtered_df["most_playedon"] == input.platform_filter()]
            
        min_dance, max_dance = input.dance_filter()
        filtered_df = filtered_df[(filtered_df["Danceability"] >= min_dance) & (filtered_df["Danceability"] <= max_dance)]
        
        min_energy, max_energy = input.energy_filter()
        filtered_df = filtered_df[(filtered_df["Energy"] >= min_energy) & (filtered_df["Energy"] <= max_energy)]
        
        min_stream_raw = input.stream_filter() * 1_000_000
        min_views_raw = input.views_filter() * 1_000_000
        filtered_df = filtered_df[
            (filtered_df["Stream"] >= min_stream_raw) & 
            (filtered_df["Views"] >= min_views_raw)
        ]
        return filtered_df

    def format_to_business_units(val):
        if pd.isna(val) or val == 0: return "0"
        if val >= 1_000_000_000: return f"{val / 1_000_000_000:.2f} B"
        if val >= 1_000_000: return f"{val / 1_000_000:.2f} M"
        if val >= 1_000: return f"{val / 1_000:.1f} K"
        return f"{val:,.0f}"

    @render.text
    def kpi_streams(): return format_to_business_units(filtered_data()['Stream'].sum())
    @render.text
    def kpi_views(): return format_to_business_units(filtered_data()['Views'].sum())
    @render.text
    def kpi_likes(): return format_to_business_units(filtered_data()['Likes'].sum())

    def get_safe_empty_fig(text="No data matches the selected filters"):
        fig = go.Figure()
        fig.add_annotation(text=text, x=0.5, y=0.5, showarrow=False, font=dict(size=18, color="#adb5bd"))
        fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False), plot_bgcolor="white")
        return fig

    # =========================================================================
    # Spotify Tab Charts
    # =========================================================================
    @render_plotly
    def spotify_bar_chart():
        dff = filtered_data()
        if dff.empty: return get_safe_empty_fig()
        
        dff['track_display'] = dff['Track'] + " (" + dff['Artist'] + ")"
        dff['track_display'] = dff['track_display'].apply(lambda x: "<br>".join(textwrap.wrap(x, width=35)))
        
        top_tracks = dff.drop_duplicates(subset=['Track']).nlargest(10, 'Stream')
        top_tracks = top_tracks.sort_values(by="Stream", ascending=True) 
        if top_tracks.empty: return get_safe_empty_fig()

        top_tracks['Label'] = top_tracks['Stream'].apply(format_to_business_units)

        
        fig = px.bar(
            top_tracks, x="Stream", y="track_display", orientation="h", 
            color="most_playedon", color_discrete_map={"Spotify": "#1DB954", "Youtube": "#FF0000"},
            text="Label", height=420 
        )
        fig.update_traces(textposition='outside', textfont_size=12, cliponaxis=False)
        fig.update_layout(
            yaxis={'categoryorder':'total ascending'}, plot_bgcolor="white",
            margin=dict(l=260, r=40, t=10, b=10), showlegend=False
        )
        fig.update_yaxes(ticklabelposition="outside left", tickfont=dict(size=12), title="")
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f1f3f5', title="") 
        return fig

    @render_plotly
    def spotify_fingerprint_chart():
        dff = filtered_data()
        if dff.empty: return get_safe_empty_fig()
        
        top_tracks = dff.drop_duplicates(subset=['Track']).nlargest(10, 'Stream')
        if top_tracks.empty: return get_safe_empty_fig()
            
        features = ['Danceability', 'Energy', 'Valence', 'Acousticness', 'Speechiness', 'Liveness']
        available = [f for f in features if f in top_tracks.columns]
        means = top_tracks[available].mean().round(3).reset_index()
        means.columns = ['Feature', 'Score']
        means = means.sort_values(by='Score', ascending=True)

        
        fig = px.bar(
            means, x='Score', y='Feature', orientation='h',
            text='Score', color='Score', color_continuous_scale='Teal', height=420
        )
        fig.update_traces(textposition='outside', textfont_size=14, cliponaxis=False)
        fig.update_layout(
            plot_bgcolor="white", margin=dict(l=100, r=40, t=20, b=10),
            coloraxis_showscale=False, showlegend=False
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f1f3f5', range=[0, 1.1], title="")
        fig.update_yaxes(title="")
        return fig

    # =========================================================================
    # YouTube Tab Charts
    # =========================================================================
    @render_plotly
    def youtube_bar_chart():
        dff = filtered_data()
        if dff.empty: return get_safe_empty_fig()
        
        dff['track_display'] = dff['Track'] + " (" + dff['Artist'] + ")"
        dff['track_display'] = dff['track_display'].apply(lambda x: "<br>".join(textwrap.wrap(x, width=35)))
        
        # Views rank
        top_tracks = dff.drop_duplicates(subset=['Track']).nlargest(10, 'Views')
        top_tracks = top_tracks.sort_values(by="Views", ascending=True) 
        if top_tracks.empty: return get_safe_empty_fig()

        top_tracks['Label'] = top_tracks['Views'].apply(format_to_business_units)

        
        fig = px.bar(
            top_tracks, x="Views", y="track_display", orientation="h", 
            color="most_playedon", color_discrete_map={"Spotify": "#1DB954", "Youtube": "#FF0000"},
            text="Label", height=420 
        )
        fig.update_traces(textposition='outside', textfont_size=12, cliponaxis=False)
        fig.update_layout(
            yaxis={'categoryorder':'total ascending'}, plot_bgcolor="white",
            margin=dict(l=260, r=40, t=10, b=10), showlegend=False
        )
        fig.update_yaxes(ticklabelposition="outside left", tickfont=dict(size=12), title="")
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f1f3f5', title="") 
        return fig

    @render_plotly
    def youtube_fingerprint_chart():
        dff = filtered_data()
        if dff.empty: return get_safe_empty_fig()
        
        top_tracks = dff.drop_duplicates(subset=['Track']).nlargest(10, 'Views')
        if top_tracks.empty: return get_safe_empty_fig()
            
        features = ['Danceability', 'Energy', 'Valence', 'Acousticness', 'Speechiness', 'Liveness']
        available = [f for f in features if f in top_tracks.columns]
        means = top_tracks[available].mean().round(3).reset_index()
        means.columns = ['Feature', 'Score']
        means = means.sort_values(by='Score', ascending=True)

        
        fig = px.bar(
            means, x='Score', y='Feature', orientation='h',
            text='Score', color='Score', color_continuous_scale='Sunset', height=420
        )
        fig.update_traces(textposition='outside', textfont_size=14, cliponaxis=False)
        fig.update_layout(
            plot_bgcolor="white", margin=dict(l=100, r=40, t=20, b=10),
            coloraxis_showscale=False, showlegend=False
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f1f3f5', range=[0, 1.1], title="")
        fig.update_yaxes(title="")
        return fig

    # =========================================================================
    # Bottom Master Scatter Chart
    # =========================================================================
    @render_plotly
    def scatter_chart():
        dff = filtered_data()
        if dff.empty: return get_safe_empty_fig()
        if len(dff) > 2000: dff = dff.sample(2000, random_state=42)
            
        fig = px.scatter(
            dff, x="Views", y="Stream",  
            color="most_playedon", color_discrete_map={"Spotify": "#1DB954", "Youtube": "#FF0000"},
            size=input.size_axis(), size_max=45, 
            hover_name="Track", 
            hover_data={"Artist": True, "most_playedon": False, input.size_axis(): True},
            labels={
                "Views": "YouTube Views", 
                "Stream": "Spotify Streams", 
                "most_playedon": "Dominant Platform",
                input.size_axis(): f"{input.size_axis()}"
            },
            log_x=True, log_y=True, height=700 
        )
        
        fig.update_traces(marker=dict(opacity=0.75, line=dict(width=0.5, color='white')))
        
        fig.update_layout(
            plot_bgcolor="white", 
            margin=dict(t=30, b=40, l=60, r=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
            font=dict(size=14)
        )
        
        
        tick_values = [1e5, 1e6, 1e7, 1e8, 1e9, 1e10]
        tick_texts = ['100K', '1M', '10M', '100M', '1B', '10B']
        
        fig.update_xaxes(
            showgrid=True, gridwidth=1, gridcolor='#f8f9fa', 
            tickvals=tick_values, ticktext=tick_texts, title="YouTube Views"
        )
        fig.update_yaxes(
            showgrid=True, gridwidth=1, gridcolor='#f8f9fa', 
            tickvals=tick_values, ticktext=tick_texts, title="Spotify Streams"
        )
        
        return fig

app = App(app_ui, server)