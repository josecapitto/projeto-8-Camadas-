"""Teste sem microfone para conferir a matematica do Projeto 8.

Este arquivo usa tres sinais artificiais somente para testar o programa. Na
apresentacao, devem ser usadas as gravacoes reais feitas pelo menu principal.
"""

from pathlib import Path
import tempfile
import wave

import numpy as np

import main


def testar_reamostragem():
    """Confere tempo, tom e antialiasing na leitura dos WAVs antigos."""
    tempo = np.arange(48_000) / 48_000
    desejado = 0.6 * np.sin(2 * np.pi * 1_000 * tempo)
    acima_nyquist = 0.3 * np.sin(2 * np.pi * 23_000 * tempo)
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / "antigo_48000.wav"
        pcm = ((desejado + acima_nyquist) * 32767).astype(np.int16)
        with wave.open(str(caminho), "wb") as arquivo:
            arquivo.setnchannels(2)
            arquivo.setsampwidth(2)
            arquivo.setframerate(48_000)
            arquivo.writeframes(np.column_stack([pcm, pcm]).tobytes())
        convertido = main.carregar_wav(caminho)
        assert len(convertido) == 44_100
        referencia = 0.6 * np.sin(2 * np.pi * 1_000 * np.arange(44_100) / 44_100)
        assert np.max(abs(convertido - referencia)) < 1e-4
        # O original permanece intacto; a conversao ocorre nas amostras.
        with wave.open(str(caminho), "rb") as arquivo:
            assert arquivo.getframerate() == 48_000


def executar_teste():
    assert main.TAXA_AMOSTRAGEM == 44_100
    testar_reamostragem()
    print("Reamostragem 48000 -> 44100 Hz: duracao e tom preservados, sem aliasing")
    duracao = 2
    tempo = np.arange(duracao * main.TAXA_AMOSTRAGEM) / main.TAXA_AMOSTRAGEM

    # Cada estacao possui uma combinacao diferente de frequencias audiveis.
    tons = [
        0.7 * np.sin(2 * np.pi * 300 * tempo)
        + 0.3 * np.sin(2 * np.pi * 700 * tempo),
        0.7 * np.sin(2 * np.pi * 450 * tempo)
        + 0.3 * np.sin(2 * np.pi * 900 * tempo),
        0.7 * np.sin(2 * np.pi * 600 * tempo)
        + 0.3 * np.sin(2 * np.pi * 1_100 * tempo),
    ]

    passa_baixa = main.filtro_passa_baixa(main.CORTE_AUDIO)
    filtrados = [main.aplicar_filtro(s, passa_baixa) for s in tons]
    modulados = [
        main.modular(s, faixa[2])
        for s, faixa in zip(filtrados, main.FAIXAS)
    ]

    for numero, (sinal, faixa) in enumerate(zip(modulados, main.FAIXAS), 1):
        energia = main.porcentagem_energia_na_faixa(
            sinal, faixa[0], faixa[1]
        )
        assert energia > 99.9, (
            f"Estacao {numero} teve apenas {energia:.6f}% dentro da faixa"
        )

    meio = np.sum(modulados, axis=0) / 3

    # Compara cada audio recuperado com seu original ja filtrado. Ignoramos as
    # bordas, onde filtros FIR sempre apresentam um pequeno transitorio.
    margem = main.TAMANHO_FILTRO
    for numero, (original, faixa) in enumerate(zip(filtrados, main.FAIXAS), 1):
        bp = main.filtro_passa_faixa(faixa[0], faixa[1])
        extraido = main.aplicar_filtro(meio, bp)
        recuperado = main.demodular(extraido, faixa[2], passa_baixa)

        a = original[margem:-margem]
        b = recuperado[margem:-margem]
        correlacao = np.corrcoef(a, b)[0, 1]
        assert correlacao > 0.99, (
            f"Estacao {numero} teve correlacao {correlacao:.6f}"
        )
        print(
            f"Estacao {numero}: energia na faixa > 99,9% e "
            f"correlacao = {correlacao:.6f}"
        )

    # Confirma tambem se a escrita e a leitura de WAV funcionam.
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / "teste.wav"
        main.salvar_wav(caminho, tons[0])
        with wave.open(str(caminho), "rb") as arquivo:
            assert arquivo.getframerate() == 44_100
        recarregado = main.carregar_wav(caminho)
        assert len(recarregado) == len(tons[0])

    print("Teste automatico concluido com sucesso.")


if __name__ == "__main__":
    executar_teste()
