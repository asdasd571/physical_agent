"""Render the README architecture PNG using the existing PyMuPDF dependency."""

from pathlib import Path
import math

import fitz


def render():
    root = Path(__file__).resolve().parents[2]
    document = fitz.open()
    page = document.new_page(width=1000, height=1400)
    page.insert_font(fontname="pretendard", fontfile=str(root / "reporting/fonts/Pretendard-Regular.ttf"))
    ink = (0.13, 0.22, 0.35)
    blue = (0.89, 0.94, 1)
    green = (0.90, 0.97, 0.93)

    def text(rect, value, size=18):
        remaining = page.insert_textbox(fitz.Rect(rect), value, fontsize=size,
                                        fontname="pretendard", align=1, color=ink)
        if remaining < 0:
            raise ValueError(f"Text does not fit: {value}")

    def box(x, y, label, width=220, fill=blue):
        rect = fitz.Rect(x-width/2, y-32, x+width/2, y+32)
        page.draw_rect(rect, color=ink, fill=fill, width=1.5)
        text((rect.x0+6, rect.y0+12, rect.x1-6, rect.y1), label)

    def arrow(points, label=None, label_rect=None):
        for start, end in zip(points, points[1:]):
            page.draw_line(start, end, color=ink, width=1.4)
        (x0, y0), (x, y) = points[-2:]
        angle = math.atan2(y-y0, x-x0)
        for delta in (-0.5, 0.5):
            page.draw_line((x, y), (x-10*math.cos(angle+delta), y-10*math.sin(angle+delta)), color=ink, width=1.4)
        if label:
            text(label_rect, label, 15)

    text((80, 15, 920, 60), "Physical AI · Supervisor Architecture", 28)
    box(500, 100, "START → Init")
    box(500, 210, "후보 선택 / Select")
    box(500, 330, "Supervisor / 근거·예산 판단", 320)
    arrow([(500,132),(500,178)])
    arrow([(500,242),(500,298)])
    # Exactly one worker is selected per dispatch; every worker returns.
    workers = [(150,"Discover"),(325,"Tech"),(500,"Market"),(675,"Competitor"),(850,"Synergy")]
    for x, label in workers:
        box(x, 510, label, 150)
        arrow([(500,362),(500,435),(x,435),(x,478)])
        arrow([(x,542),(x,585),(50,585),(50,330),(340,330)])
    text((520,385,930,420), "부족한 관점의 담당자 1명 호출", 17)
    text((130,596,860,632), "모든 담당자 → Supervisor 복귀 · 필요 시 재조사", 17)
    box(370, 690, "Judge / 투자 규칙")
    box(770, 690, "Skip / 심층 평가 보류")
    arrow([(660,330),(950,330),(950,650),(370,650),(370,658)],
          "근거 검토 완료 / 조사 한도", (340,620,680,645))
    arrow([(950,650),(770,650),(770,658)])
    text((700,610,940,638), "적격성 제외 / 확인 불가", 15)
    box(370, 800, "Narrative / 근거 해설")
    arrow([(370,722),(370,768)])
    box(500, 900, "Archive / 후보 결과 저장", 280)
    arrow([(370,832),(370,850),(500,850),(500,868)])
    arrow([(770,722),(770,850),(500,850)])
    arrow([(640,900),(970,900),(970,210),(610,210)])
    text((700,865,950,891), "다음 후보가 있으면 반복", 15)
    box(500, 1010, "Report / PDF·JSON 생성", 280)
    arrow([(500,932),(500,978)], "모든 후보 완료", (530,940,750,966))
    box(500, 1120, "Quality / 규칙 기반 평가", 280)
    arrow([(500,1042),(500,1088)])
    box(830, 1120, "Revise / 재작성", 240, green)
    arrow([(640,1120),(710,1120)], "미달·수정 여유 있음", (645,1050,950,1080))
    arrow([(830,1088),(830,1010),(640,1010)])
    text((715,950,960,987), "원값·출처 유지 / 최대 2회", 15)
    box(500, 1240, "Finalize / 결과 저장", 280, green)
    arrow([(500,1152),(500,1208)], "통과 또는 수정 한도", (520,1165,810,1196))
    box(500, 1340, "END / passed·quality_failed", 340, green)
    arrow([(500,1272),(500,1308)])
    page.get_pixmap(matrix=fitz.Matrix(1.5,1.5), alpha=False).save(root / "docs/supervisor/architecture.png")
    document.close()


if __name__ == "__main__":
    render()
