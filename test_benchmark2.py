import time
import pandas as pd
import numpy as np
import io

def original_df_to_pdf(title: str, df: pd.DataFrame) -> bytes:
    try:
        from fpdf import FPDF
        df = df.where(pd.notna(df), "")   # evita "nan" no PDF
        pdf = FPDF(orientation="L")   # paisagem — comporta mais colunas
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, str(title)[:50], new_x="LMARGIN", new_y="NEXT", align="C")
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
    except Exception as e:
        print(f"Error original: {e}")
        return b"", 0

def optimized_df_to_pdf(title: str, df: pd.DataFrame) -> bytes:
    try:
        from fpdf import FPDF
        df = df.where(pd.notna(df), "")   # evita "nan" no PDF
        pdf = FPDF(orientation="L")   # paisagem — comporta mais colunas
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, str(title)[:50], new_x="LMARGIN", new_y="NEXT", align="C")
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

        for i, row in enumerate(df.itertuples(index=False)):
            if i % 2 == 0:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)
            # row is a tuple, we can iterate directly over it
            for val in row:
                pdf.cell(col_w, 5, str(val)[:22], border=1, fill=True)
            pdf.ln()

        iteration_time = time.time() - start_time

        out = pdf.output()
        return bytes(out), iteration_time
    except Exception as e:
        print(f"Error optimized: {e}")
        return b"", 0

def run_benchmark():
    # Use different sizes
    sizes = [100, 500, 2000]

    for size in sizes:
        print(f"\n--- Benchmarking with {size} rows ---")
        # Ensure we have mixed types to test type conversion overhead
        data = {
            "ID": range(size),
            "Name": [f"Item {i}" for i in range(size)],
            "Value1": np.random.randn(size),
            "Value2": np.random.randint(0, 100, size),
            "Category": np.random.choice(["A", "B", "C"], size)
        }
        df = pd.DataFrame(data)

        # Original
        t0 = time.time()
        out_orig, orig_iter_time = original_df_to_pdf(f"Test {size}", df)
        t1 = time.time()
        orig_total_time = t1 - t0
        print(f"Original total time: {orig_total_time:.4f}s (Iteration time: {orig_iter_time:.4f}s)")

        # Optimized
        t0 = time.time()
        out_opt, opt_iter_time = optimized_df_to_pdf(f"Test {size}", df)
        t1 = time.time()
        opt_total_time = t1 - t0
        print(f"Optimized total time: {opt_total_time:.4f}s (Iteration time: {opt_iter_time:.4f}s)")

        print(f"Total Speedup: {orig_total_time / opt_total_time:.2f}x")
        print(f"Iteration Loop Speedup: {orig_iter_time / opt_iter_time:.2f}x")

if __name__ == "__main__":
    run_benchmark()
