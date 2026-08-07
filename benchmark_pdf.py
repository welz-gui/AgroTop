import time
import pandas as pd
import numpy as np

# A duplicate of the original function to benchmark
def original_df_to_pdf(title: str, df: pd.DataFrame) -> bytes:
    try:
        from fpdf import FPDF
        df = df.where(pd.notna(df), "")   # evita "nan" no PDF
        pdf = FPDF(orientation="L")   # paisagem — comporta mais colunas
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, title[:50], ln=True, align="C")
        pdf.set_font("Helvetica", "", 6)
        cols  = list(df.columns)
        n     = max(len(cols), 1)
        col_w = max(min(277 // n, 45), 12)   # largura útil em paisagem ~277mm
        # Cabeçalho
        pdf.set_fill_color(30, 60, 30)
        pdf.set_text_color(200, 255, 200)
        pdf.set_font("Helvetica", "B", 6)
        for col in cols:
            pdf.cell(col_w, 6, str(col)[:22], border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(20, 20, 20)

        start_time = time.time()
        for i, row in df.iterrows():
            if i % 2 == 0:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)
            for col in cols:
                pdf.cell(col_w, 5, str(row[col])[:22], border=1, fill=True)
            pdf.ln()
        iteration_time = time.time() - start_time

        out = pdf.output()
        return bytes(out), iteration_time
    except ImportError:
        return b"", 0
    except Exception:
        # Falha inesperada não deve derrubar a página de relatórios
        return b"", 0

def optimized_df_to_pdf(title: str, df: pd.DataFrame) -> bytes:
    try:
        from fpdf import FPDF
        df = df.where(pd.notna(df), "")   # evita "nan" no PDF
        pdf = FPDF(orientation="L")   # paisagem — comporta mais colunas
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, title[:50], ln=True, align="C")
        pdf.set_font("Helvetica", "", 6)
        cols  = list(df.columns)
        n     = max(len(cols), 1)
        col_w = max(min(277 // n, 45), 12)   # largura útil em paisagem ~277mm
        # Cabeçalho
        pdf.set_fill_color(30, 60, 30)
        pdf.set_text_color(200, 255, 200)
        pdf.set_font("Helvetica", "B", 6)
        for col in cols:
            pdf.cell(col_w, 6, str(col)[:22], border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(20, 20, 20)

        start_time = time.time()

        # Use itertuples which is much faster than iterrows
        for i, row in enumerate(df.itertuples(index=False)):
            if i % 2 == 0:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)
            for val in row:
                pdf.cell(col_w, 5, str(val)[:22], border=1, fill=True)
            pdf.ln()

        iteration_time = time.time() - start_time

        out = pdf.output()
        return bytes(out), iteration_time
    except ImportError:
        return b"", 0
    except Exception:
        # Falha inesperada não deve derrubar a página de relatórios
        return b"", 0


def run_benchmark():
    print("Generating large test dataframe...")
    # Create a DataFrame with 1000 rows and 10 columns
    df = pd.DataFrame(np.random.randint(0, 100, size=(1000, 10)), columns=[f"Col_{i}" for i in range(10)])

    print("Benchmarking original iterrows implementation...")
    # Warmup
    original_df_to_pdf("Warmup", df.head(10))

    # Run
    t0 = time.time()
    _, orig_iter_time = original_df_to_pdf("Test Original", df)
    t1 = time.time()
    orig_total_time = t1 - t0
    print(f"Original total time: {orig_total_time:.4f}s (Iteration time: {orig_iter_time:.4f}s)")

    print("Benchmarking optimized itertuples implementation...")
    # Warmup
    optimized_df_to_pdf("Warmup", df.head(10))

    # Run
    t0 = time.time()
    _, opt_iter_time = optimized_df_to_pdf("Test Optimized", df)
    t1 = time.time()
    opt_total_time = t1 - t0
    print(f"Optimized total time: {opt_total_time:.4f}s (Iteration time: {opt_iter_time:.4f}s)")

    speedup_total = orig_total_time / opt_total_time
    speedup_iter = orig_iter_time / opt_iter_time

    print(f"Total Speedup: {speedup_total:.2f}x")
    print(f"Iteration Loop Speedup: {speedup_iter:.2f}x")

if __name__ == "__main__":
    run_benchmark()
