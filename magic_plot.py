from pydantic import BaseModel
from ollama import chat
import duckdb
from smolagents.local_python_executor import LocalPythonExecutor

def magic_plot(con: duckdb.DuckDBPyConnection, prompt: str):
    """Generate a plot of the data in `con` from natural language description `prompt`.

    Args:
        con: A DuckDBPyConnection object.
        prompt: A string containing the natural language description of the plot to generate.

    Example:
        >> import duckdb
        >> con = duckdb.connect("file.db")
        >> magic_plot(con, "Plot monthly sales revenue by product line")
    """
    df = run_sql_code(con, prompt)
    custom_executor = LocalPythonExecutor(["matplotlib.pyplot", "seaborn"])
    custom_executor.send_variables({'df': df})
    run_seaborn_code(custom_executor, df, prompt)

class MotivatedCode(BaseModel):
  reasoning: str
  code: str

class Code(BaseModel):
  code: str

def table_summary(con: duckdb.DuckDBPyConnection):
    "Summarize all table columns in a Markdown list"
    table_info = con.sql("show all tables").df()
    def summary_rows():
        for row in table_info.itertuples(index=False):
            yield from [f"Table {row.name}"] + [f"- {r}: {t}" for (r, t) in zip(row.column_names, row.column_types)]
    return "\n".join(summary_rows())

def run_sql_code(con: duckdb.DuckDBPyConnection, prompt: str):
    response = chat(
      model='qwen3:8b',
      messages=[{'role': 'user', 'content':
                 f"""Generate duckdb sql code to get data necessary for the following:
                 {prompt}

                 Tables are defined as follows:
                 {table_summary(con)}
                 Check that your code is valid sql before returning; ensure that
                 all selected columns are accounted for by "group by" expressions if they exist.
                 """}],
      format=MotivatedCode.model_json_schema(),
      options={'temperature': 0},  # Make responses more deterministic
    )
    query = Code.model_validate_json(response.message.content)
    return con.sql(query.code).df()

def run_seaborn_code(custom_executor, df, prompt):
    response = chat(
      model='qwen3:8b',
      messages=[{'role': 'user', 'content':
                 f"""Define a python function `plotit(df: DataFrame)` using seaborn code for the following:
                 {prompt}

                 The input dataframe has the following columns:
                 {df.columns}
                 Do not process, pivot, or group the data.
                 """}],
      format=Code.model_json_schema(),
      options={'temperature': 0},  # Make responses more deterministic
    )
    vis_code = Code.model_validate_json(response.message.content)
    custom_executor(vis_code.code)
    custom_executor("plotit(df)")
