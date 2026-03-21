"""
터미널 대시보드 - rich 라이브러리 기반 결과 출력
"""

from datetime import datetime

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class Dashboard:
    """
    Product Radar 결과 대시보드

    rich 설치 시: 컬러풀한 테이블 출력
    미설치 시: 기본 텍스트 출력
    """

    def __init__(self):
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

    def print_header(self, text: str) -> None:
        if RICH_AVAILABLE:
            self.console.print(
                Panel(
                    f"[bold cyan]🎯 {text}[/bold cyan]",
                    border_style="cyan",
                    padding=(1, 2),
                )
            )
        else:
            print(f"\n{'='*60}")
            print(f"  🎯 {text}")
            print(f"{'='*60}")

    def print_step(self, step_num: int, text: str) -> None:
        if RICH_AVAILABLE:
            self.console.print(f"\n[bold yellow]▶ Step {step_num}[/bold yellow] [white]{text}[/white]")
        else:
            print(f"\n▶ Step {step_num}: {text}")

    def print_info(self, text: str) -> None:
        if RICH_AVAILABLE:
            self.console.print(f"  [dim]→[/dim] {text}")
        else:
            print(f"  → {text}")

    def print_error(self, text: str) -> None:
        if RICH_AVAILABLE:
            self.console.print(f"  [red]✗ {text}[/red]")
        else:
            print(f"  ✗ ERROR: {text}")

    def print_results(self, products: list[dict]) -> None:
        """상위 상품 결과 테이블 출력"""
        if not products:
            self.print_info("결과 없음")
            return

        if RICH_AVAILABLE:
            self._print_rich_table(products)
        else:
            self._print_plain_table(products)

    def _print_rich_table(self, products: list[dict]) -> None:
        """rich 테이블 출력"""
        console = self.console

        console.print(f"\n[bold green]🏆 레이더 포착 상품 TOP {len(products)}[/bold green]\n")

        # 요약 통계
        spike_count = sum(1 for p in products if p["scores"].get("is_24h_spike"))
        repeat_count = sum(1 for p in products if p["scores"].get("is_3d_repeat"))
        console.print(
            f"  [cyan]⚡ 24h 급등[/cyan]: {spike_count}개  "
            f"[magenta]🔁 3d 반복[/magenta]: {repeat_count}개  "
            f"[yellow]총 상품[/yellow]: {len(products)}개\n"
        )

        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            border_style="bright_black",
            title=f"Product Radar Results — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        )

        # 컬럼 정의
        table.add_column("#", style="dim", width=3, justify="right")
        table.add_column("상품명", style="white", min_width=30, max_width=40)
        table.add_column("카테고리", style="cyan", width=10)
        table.add_column("종합\n점수", style="bold", width=8, justify="center")
        table.add_column("바이럴\n점수", style="magenta", width=8, justify="center")
        table.add_column("트렌드\n점수", style="yellow", width=8, justify="center")
        table.add_column("마진율", style="green", width=8, justify="center")
        table.add_column("판매가", style="green", width=8, justify="center")
        table.add_column("배송", style="blue", width=6, justify="center")
        table.add_column("등급", style="bold", width=5, justify="center")
        table.add_column("시그널", width=12)

        for i, item in enumerate(products, 1):
            product = item["product"]
            scores = item["scores"]
            pricing = scores.get("commercial", {}).get("pricing", {})
            margin = pricing.get("margin_pct", 0)
            sell_price = pricing.get("sell_price", 0)
            shipping_days = product.get("shipping_days", 0)
            viral_grade = scores.get("viral_grade", "?")

            # 시그널 표시
            signals = []
            if scores.get("is_24h_spike"):
                signals.append("⚡급등")
            if scores.get("is_3d_repeat"):
                signals.append("🔁반복")
            signal_text = " ".join(signals) if signals else "-"

            # 점수 색상
            total = scores.get("total_score", 0)
            if total >= 80:
                score_style = "bold green"
            elif total >= 65:
                score_style = "green"
            else:
                score_style = "yellow"

            # 등급 색상
            grade_colors = {"S": "bold red", "A": "bold yellow", "B": "green", "C": "cyan", "D": "dim"}
            grade_style = grade_colors.get(viral_grade, "white")

            table.add_row(
                str(i),
                product.get("title", "")[:38],
                product.get("category", ""),
                Text(f"{total:.0f}", style=score_style),
                f"{scores.get('viral_score', 0):.0f}",
                f"{scores.get('trend_score', 0):.0f}",
                f"{margin:.0f}%",
                f"${sell_price:.2f}",
                f"{shipping_days}일",
                Text(viral_grade, style=grade_style),
                signal_text,
            )

        console.print(table)

        # 상위 3개 상세 정보
        console.print("\n[bold cyan]📊 TOP 3 상품 상세[/bold cyan]\n")
        for i, item in enumerate(products[:3], 1):
            self._print_product_detail(i, item)

    def _print_product_detail(self, rank: int, item: dict) -> None:
        """개별 상품 상세 패널 출력"""
        product = item["product"]
        scores = item["scores"]
        pricing = scores.get("commercial", {}).get("pricing", {})

        title = product.get("title", "")[:60]
        total = scores.get("total_score", 0)
        viral = scores.get("viral_score", 0)
        trend = scores.get("trend_score", 0)
        profit = scores.get("profit_score", 0)
        quality = scores.get("quality_score", 0)
        shipping = scores.get("shipping_score", 0)

        sell_price = pricing.get("sell_price", 0)
        margin = pricing.get("margin_pct", 0)
        roas = pricing.get("estimated_roas", 0)
        ship_days = product.get("shipping_days", 0)
        recommendation = scores.get("commercial", {}).get("recommendation", "")

        signals = []
        if scores.get("is_24h_spike"):
            spike_ratio = scores.get("spike_ratio", 0)
            signals.append(f"⚡ 24h 급등 ({spike_ratio:.1f}x)")
        if scores.get("is_3d_repeat"):
            repeat_days = scores.get("repeat_days", 0)
            signals.append(f"🔁 {repeat_days}일 반복 트렌드")
        signal_str = "  |  ".join(signals) if signals else "일반 트렌드"

        content = (
            f"[bold white]{title}[/bold white]\n\n"
            f"[dim]소스: {product.get('source', '')} | "
            f"공급업체: {product.get('supplier', '')} | "
            f"배송: {ship_days}일[/dim]\n\n"
            f"[yellow]시그널:[/yellow] {signal_str}\n\n"
            f"[cyan]점수 분포:[/cyan]\n"
            f"  바이럴: [magenta]{viral:.0f}[/magenta]  트렌드: [yellow]{trend:.0f}[/yellow]  "
            f"수익성: [green]{profit:.0f}[/green]  품질: [blue]{quality:.0f}[/blue]  "
            f"배송: [cyan]{shipping:.0f}[/cyan]\n\n"
            f"[green]가격 전략:[/green] ${sell_price:.2f} 판매 | 마진 {margin:.0f}% | 예상 ROAS {roas:.1f}x\n"
            f"[dim]{recommendation}[/dim]"
        )

        self.console.print(
            Panel(
                content,
                title=f"[bold cyan]#{rank} 종합 {total:.0f}점[/bold cyan]",
                border_style="cyan" if rank == 1 else "bright_black",
                padding=(0, 1),
            )
        )

    def _print_plain_table(self, products: list[dict]) -> None:
        """plain 텍스트 출력 (rich 없을 때)"""
        print(f"\n{'='*80}")
        print(f"  🏆 레이더 포착 상품 TOP {len(products)}")
        print(f"{'='*80}")
        print(f"{'#':<3} {'상품명':<40} {'점수':>5} {'마진':>6} {'배송':>5} {'시그널':<15}")
        print(f"{'-'*80}")

        for i, item in enumerate(products, 1):
            product = item["product"]
            scores = item["scores"]
            pricing = scores.get("commercial", {}).get("pricing", {})

            title = product.get("title", "")[:38]
            total = scores.get("total_score", 0)
            margin = pricing.get("margin_pct", 0)
            ship_days = product.get("shipping_days", 0)

            signals = []
            if scores.get("is_24h_spike"):
                signals.append("⚡급등")
            if scores.get("is_3d_repeat"):
                signals.append("🔁반복")
            signal_text = " ".join(signals) if signals else "-"

            print(f"{i:<3} {title:<40} {total:>5.1f} {margin:>5.0f}% {ship_days:>4}일 {signal_text:<15}")

        print(f"{'='*80}\n")
