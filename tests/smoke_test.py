"""Smoke test headless de PokePikas.

Valida lo mínimo para detectar regresiones estructurales sin abrir la GUI:

1. Los JSON versionados cargan y mantienen el tamaño esperado.
2. Los cinco agentes pueden elegir una acción legal sobre un estado real.
3. Una batalla completa 3v3 termina por KO dentro del límite de turnos.

Uso:
    python tests/smoke_test.py
"""

import random
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.ai.level1_agent import Level1Agent
from src.ai.level2_agent import Level2Agent
from src.ai.level3_agent import Level3Agent
from src.ai.level4_agent import Level4Agent
from src.ai.level5_agent import Level5Agent
from src.core.battle_engine import process_turn
from src.core.interfaces import Action, ActionType, BattleState
from src.utils.move_registry import get_data_loader

POKEMON_PATH = ROOT_DIR / "data" / "pokemon_pool.json"
MOVES_PATH = ROOT_DIR / "data" / "moves_pool.json"
MAX_TURNS = 120


def check_data() -> None:
    """Comprueba que el catálogo versionado esté completo y sea consistente."""
    loader = get_data_loader(str(POKEMON_PATH), str(MOVES_PATH))
    assert len(loader.pokemon_data) == 30, "se esperaban 30 Pokémon en el pool"
    assert len(loader.moves_data) == 95, "se esperaban 95 movimientos en el pool"

    move_ids = {move["id"] for move in loader.moves_data}
    for pokemon in loader.pokemon_data:
        assert pokemon["move_ids"], f"{pokemon['name']} no tiene movimientos"
        assert set(pokemon["move_ids"]) <= move_ids, (
            f"{pokemon['name']} referencia movimientos inexistentes"
        )
    print(f"[OK] datos: {len(loader.pokemon_data)} Pokémon, {len(loader.moves_data)} movimientos")


def build_state(loader, team_size: int = 3) -> BattleState:
    """Crea un BattleState 3v3 determinista para probar a los agentes."""
    random.seed(2026)
    p1_team = loader.generate_random_team(team_size)
    p2_team = loader.generate_random_team(team_size)
    return BattleState(
        p1_team=[p.to_state() for p in p1_team],
        p2_team=[p.to_state() for p in p2_team],
        p1_active_index=0,
        p2_active_index=0,
        turn_number=1,
    )


def check_agents() -> None:
    """Verifica que L1-L5 devuelvan una Action válida sobre el mismo estado."""
    loader = get_data_loader(str(POKEMON_PATH), str(MOVES_PATH))
    state = build_state(loader)

    for agent_cls in (Level1Agent, Level2Agent, Level3Agent, Level4Agent, Level5Agent):
        agent = agent_cls(player_id=1)
        action = agent.get_action(state)
        assert isinstance(action, Action), f"{agent_cls.__name__} no devolvió Action"
        assert isinstance(action.type, ActionType), (
            f"{agent_cls.__name__} devolvió un tipo de acción inválido"
        )
        print(f"[OK] {agent_cls.__name__} -> {action.type.value} target={action.target_index}")


def check_full_battle() -> None:
    """Ejecuta una batalla 3v3 completa (L5 vs L1) y valida el resultado."""
    random.seed(7)
    loader = get_data_loader(str(POKEMON_PATH), str(MOVES_PATH))
    p1_team = loader.generate_random_team(3)
    p2_team = loader.generate_random_team(3)

    agent_p1 = Level5Agent(player_id=1)
    agent_p2 = Level1Agent(player_id=2)
    p1_idx = p2_idx = 0
    result = None
    turns_played = 0

    for turn in range(1, MAX_TURNS + 1):
        turns_played = turn
        state = BattleState(
            p1_team=[p.to_state() for p in p1_team],
            p2_team=[p.to_state() for p in p2_team],
            p1_active_index=p1_idx,
            p2_active_index=p2_idx,
            turn_number=turn,
        )
        action_p1 = agent_p1.get_action(state)
        action_p2 = agent_p2.get_action(state)
        result, p1_idx, p2_idx = process_turn(
            p1_team, p1_idx, action_p1, p2_team, p2_idx, action_p2
        )
        if result.match_over:
            break

    assert result is not None and result.match_over, (
        f"la batalla no terminó en {MAX_TURNS} turnos"
    )
    assert result.winner in (1, 2), f"ganador inesperado: {result.winner}"

    for pokemon in p1_team + p2_team:
        assert 0 <= pokemon.current_hp <= pokemon.max_hp, (
            f"HP fuera de rango para {pokemon.name}: {pokemon.current_hp}/{pokemon.max_hp}"
        )

    losing_team = p2_team if result.winner == 1 else p1_team
    assert all(p.is_fainted() for p in losing_team), "el equipo perdedor conserva Pokémon vivos"

    print(
        f"[OK] batalla 3v3: ganador=P{result.winner} "
        f"turnos={turns_played} acciones={len(result.outcomes)}"
    )


def main() -> None:
    """Ejecuta todas las comprobaciones del smoke test."""
    check_data()
    check_agents()
    check_full_battle()
    print("[OK] smoke test headless completado")


if __name__ == "__main__":
    main()
