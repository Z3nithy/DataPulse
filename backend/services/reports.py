import csv
import io

from models import Report


def report_csv(report: Report) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["grupo", "registros", "valor", "soma", "media", "minimo", "maximo"])
    result = report.result
    for row in result["groups"] or [result]:
        group = " | ".join(f"{key}: {value}" for key, value in row.get("group", {}).items())
        if group.lstrip().startswith(("=", "+", "-", "@")):
            group = "'" + group
        writer.writerow([group, row["count"], row["value"], *row["statistics"].values()])
    return "\ufeff" + output.getvalue()
