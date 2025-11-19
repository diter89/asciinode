from multiprocessing.context import SpawnContext
from asciinode.ascii_diagram import Diagram as _basediagram
from rich import print


class Diagram(_basediagram):
    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("connector_style", "[#888888 bold]")
        super().__init__(*args, **kwargs)


def create_blockchain_ecosystem() -> Diagram:
    diagram = Diagram(
        "Blockchain Ecosystem with DeFi & Layer-2 Scaling",
        allow_intersections=False,
        horizontal_spacing=7,
        vertical_spacing=5,
        box_style="square",
    )

    bitcoin = diagram.add("₿ Bitcoin")
    ethereum = bitcoin.add_right("⧫ Ethereum")
    solana = ethereum.add_right("◎ Solana")

    arbitrum = ethereum.add_bottom(" Arbitrum")
    optimism = arbitrum.add_right("  Optimism")
    polygon = optimism.add_right("  Polygon")

    uniswap = arbitrum.add_bottom("  Uniswap")
    aave = uniswap.add_right("  Aave")
    compound = aave.add_right("  Compound")

    sushiswap = uniswap.add_bottom(" SushiSwap")
    curve = sushiswap.add_right(" Curve Finance")
    balancer = curve.add_right(" Balancer")

    makerdao = aave.add_bottom(" MakerDAO")
    compound_v2 = compound.add_bottom(" Compound v2")

    opensea = diagram.add_left(" OpenSea")
    blur = opensea.add_bottom(" Blur")
    looksrare = blur.add_right(" LooksRare")

    layerzero = diagram.add_right(" LayerZero")
    wormhole = layerzero.add_bottom(" Wormhole")
    axelar = wormhole.add_right(" Axelar")

    chainlink = diagram.add_bottom(" Chainlink")
    the_graph = chainlink.add_right(" The Graph")
    pyth = the_graph.add_right(" Pyth Network")

    lido = chainlink.add_bottom(" Lido Finance")
    rocketpool = lido.add_right(" Rocket Pool")
    frax_ether = rocketpool.add_right(" Frax Ether")

    binance = diagram.add_left(" Binance")
    coinbase = binance.add_bottom(" Coinbase")
    kraken = coinbase.add_right(" Kraken")

    metamask = binance.add_left(" MetaMask")
    phantom = metamask.add_bottom(" Phantom")
    walletconnect = phantom.add_right(" WalletConnect")

    diagram.connect(bitcoin, ethereum, label="wBTC", bidirectional=True)
    diagram.connect(ethereum, solana, label="cross-chain", bidirectional=True)
    diagram.connect(ethereum, arbitrum, label="bridged ETH", bidirectional=True)
    diagram.connect(
        arbitrum, optimism, label="L2 bridge", bidirectional=True, style="[blue bold]"
    )

    diagram.connect(uniswap, aave, label="liquidity", bidirectional=True, style="[red]")
    diagram.connect(
        aave, compound, label="yield farming", bidirectional=True, style="[red]"
    )
    diagram.connect(
        uniswap, sushiswap, label="LP migration", bidirectional=True, style="[green]"
    )
    diagram.connect(
        curve, balancer, label="stable swaps", bidirectional=True, style="[green]"
    )

    diagram.connect(opensea, blur, label="listings", bidirectional=True)
    diagram.connect(blur, looksrare, label="bids", bidirectional=True)
    diagram.connect(opensea, ethereum, label="minting", bidirectional=True)

    diagram.connect(chainlink, uniswap, label="price feeds", bidirectional=True)
    diagram.connect(chainlink, aave, label="oracle data", bidirectional=True)
    diagram.connect(the_graph, uniswap, label="subgraph queries", bidirectional=True)
    diagram.connect(
        pyth, solana, label="low-latency data", bidirectional=True, style="[yellow]"
    )

    diagram.connect(layerzero, ethereum, label="omnichain", bidirectional=True)
    diagram.connect(wormhole, solana, label="message passing", bidirectional=True)
    diagram.connect(axelar, polygon, label="interchain", bidirectional=True)

    diagram.connect(lido, ethereum, label="stETH", bidirectional=True)
    diagram.connect(
        rocketpool, ethereum, label="rETH", bidirectional=True, style="[#0a7e89]"
    )
    diagram.connect(frax_ether, ethereum, label="frxETH", bidirectional=True)

    diagram.connect(binance, bitcoin, label="trading pairs", bidirectional=True)
    diagram.connect(coinbase, ethereum, label="ETH staking", bidirectional=True)
    diagram.connect(kraken, solana, label="SOL trading", bidirectional=True)

    diagram.connect(metamask, ethereum, label="dApp connections", bidirectional=True)
    diagram.connect(phantom, solana, label="SOL dApps", bidirectional=True)
    diagram.connect(walletconnect, uniswap, label="mobile trading", bidirectional=True)

    diagram.connect(makerdao, aave, label="collateral", bidirectional=True)
    diagram.connect(compound, curve, label="yield optimization", bidirectional=True)
    diagram.connect(lido, aave, label="staked collateral", bidirectional=True)

    return diagram


def main():
    print("Generating Blockchain Ecosystem Diagram...")
    diagram = create_blockchain_ecosystem()

    result = diagram.render(include_markup=True, fit_to_terminal=True)
    print(result)


if __name__ == "__main__":
    main()
