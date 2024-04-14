# read the log files to dataframes
import pandas as pd
from pathlib import Path
import plotly.express as px
import dash
from dash import html, dcc, Input, Output

log_dir = Path("logs")


def read_logs(log_dir):
    log_files = log_dir.glob("*.txt")

    data = []
    for log_file in log_files:
        training_id = (
            log_file.stem
        )  # use the file name without extension as the training identifier
        with open(log_file) as f:
            for line in f:
                start, end, exercise, count = line.split()
                data.append(
                    {
                        "training_id": training_id,
                        "start": start,
                        "end": end,
                        "exercise": exercise,
                        "count": int(count),
                    }
                )

    df = pd.DataFrame(data)

    df["start"] = pd.to_datetime(df["start"], format="%Y-%m-%d-%H-%M-%S")
    df["end"] = pd.to_datetime(df["end"], format="%Y-%m-%d-%H-%M-%S")
    df["training_id"] = pd.to_datetime(df["training_id"], format="%Y-%m-%d-%H-%M-%S")

    # normalize start and end times to start from 0 for each training

    # first get the start time for each training
    training_start = df.groupby("training_id")["start"].min().reset_index()
    training_start

    # start and end times are dates, now just substract the training start time from each

    # merge the training_start dataframe with the original dataframe
    df = pd.merge(df, training_start, on="training_id", suffixes=("", "_min"))

    # subtract the training start time from the start and end times
    df["start"] = df["start"] - df["start_min"]
    df["end"] = df["end"] - df["start_min"]

    # get 00:00:00 as the start time for each training

    now = pd.to_datetime("00:00:00", format="%H:%M:%S")
    # convert datetime deltas to datetimes
    df["start"] = df["start"].apply(lambda x: now + x)
    df["end"] = df["end"].apply(lambda x: now + x)

    df["duration"] = df["end"] - df["start"]
    df["duration"] = df["duration"].dt.total_seconds()

    # get the total repetitions of each exercise
    exercise_stats = df.groupby(["training_id", "exercise"]).agg(
        total_duration=("duration", "sum"),
        total_repetitions=("count", "sum"),
        number_of_sets=("count", "count"),
        min_repetitions=("count", "min"),
        max_repetitions=("count", "max"),
    )

    return df, exercise_stats


df, exercise_stats = read_logs(log_dir)

app = dash.Dash(__name__)

app.layout = html.Div(
    [
        html.H1("Workout Dashboard"),
        html.Div(
            [
                html.Label("Select training"),
                dcc.DatePickerRange(
                    id="date-picker-range",
                    start_date=df["training_id"].min(),
                    end_date=df["training_id"].max(),
                ),
            ]
        ),
        html.Div(
            [
                dcc.Graph(id="exercise-graph"),
            ]
        ),
        html.Div(id="stats"),
    ]
)


@app.callback(
    Output("stats", "children"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
)
def update_stats(start_date, end_date):
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    filtered_exercise_stats = exercise_stats.loc[
        (exercise_stats.index.get_level_values(0) >= start_date)
        & (exercise_stats.index.get_level_values(0) <= end_date)
    ]
    all_plots = []
    for exercise in filtered_exercise_stats.index.get_level_values(1).unique():
        plots = []

        per_exercise_stats = filtered_exercise_stats.loc[
            filtered_exercise_stats.index.get_level_values(1) == exercise
        ]

        fig = px.line(
            per_exercise_stats,
            x=per_exercise_stats.index.get_level_values(0),
            y="total_repetitions",
            title=f"Total repetitions of {exercise}",
        )
        graph = dcc.Graph(figure=fig)
        plots.append(graph)

        fig = px.line(
            per_exercise_stats,
            x=per_exercise_stats.index.get_level_values(0),
            y="number_of_sets",
            title=f"Total number of sets of {exercise}",
        )
        graph = dcc.Graph(figure=fig)
        plots.append(graph)

        fig = px.line(
            per_exercise_stats,
            x=per_exercise_stats.index.get_level_values(0),
            y="total_duration",
            title=f"Total duration of {exercise}",
        )
        graph = dcc.Graph(figure=fig)
        plots.append(graph)

        all_plots.append(
            html.Div(
                plots,
                style={"display": "flex", "flex-direction": "row", "flex-wrap": "wrap"},
            )
        )
    return all_plots


@app.callback(
    Output("exercise-graph", "figure"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
)
def update_graph(start_date, end_date):
    print(start_date, end_date)
    # Convert start_date and end_date to datetime if they are not
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    # Filter df based on start_date and end_date
    mask = (df["training_id"] >= start_date) & (df["training_id"] <= end_date)
    filtered_df = df.loc[mask]

    fig = px.timeline(
        filtered_df,
        x_start="start",
        x_end="end",
        y="training_id",
        color="exercise",
        hover_name="exercise",
        hover_data={
            "count": True,
            "start": False,
            "end": False,
            "training_id": False,
            "exercise": False,
        },
        text="count",
    )

    # dont include date in x-axis
    fig.update_xaxes(tickformat="%H:%M:%S", title_text="Time")
    fig.update_yaxes(
        tickformat="%Y-%m-%d",  # format y-axis as dates
        dtick="D1",  # show every date
    )

    fig.update_layout(
        title="Workout",
        xaxis_title="Time",
        yaxis_title="Training",
    )

    return fig


if __name__ == "__main__":
    app.run_server(debug=True)
