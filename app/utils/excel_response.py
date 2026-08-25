# Excel 响应助手

"""构造 Excel 文件下载响应（三个导出路由共用）。"""

from urllib.parse import quote

from fastapi.responses import Response

EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def excel_response(output_bytes: bytes, filename: str) -> Response:
    """
    构造 Excel 文件下载响应。

    Args:
        output_bytes: Excel 文件字节
        filename: 下载文件名（不含扩展名或含均可）

    返回带 RFC 5987 编码中文文件名的 Response。
    """
    if not filename.endswith(".xlsx"):
        filename = f"{filename}.xlsx"
    encoded_filename = quote(filename)
    return Response(
        content=output_bytes,
        media_type=EXCEL_MEDIA_TYPE,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )