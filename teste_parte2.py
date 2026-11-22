"""Testes automaticos da Parte 2 sem microfone e sem alto-falante."""

from pathlib import Path
import tempfile
from unittest.mock import patch

import numpy as np

import parte2_psk as psk


def testar_conversoes():
    texto = "Ola, engenharia! PSK numero 8."
    quadro = psk.montar_quadro(texto)
    recuperado, usados = psk.interpretar_quadro(quadro)
    assert recuperado == texto
    assert usados == len(quadro)


def testar_taxa_util_e_duracao():
    """Mede os tempos a partir das amostras, incluindo texto UTF-8."""
    for taxa in [50, 100, 200]:
        duracoes = []
        for texto in ["A", "AB", "ação"]:
            sinal, bits = psk.criar_audio_da_mensagem(texto, taxa, 4_000)
            fisica = taxa * 3
            bytes_texto = len(texto.encode("utf-8"))
            duracao_dados = bytes_texto * 8 * psk.REPETICOES * (psk.TAXA_AMOSTRAGEM // fisica)
            assert bytes_texto * 8 / (duracao_dados / psk.TAXA_AMOSTRAGEM) == taxa
            esperado = (len(bits) / fisica + psk.SILENCIO_INICIAL + psk.SILENCIO_FINAL)
            assert abs(len(sinal) / psk.TAXA_AMOSTRAGEM - esperado) < 1e-12
            duracoes.append(len(sinal) / psk.TAXA_AMOSTRAGEM)
        assert abs((duracoes[1] - duracoes[0]) - 8 / taxa) < 1e-12
        assert psk.banda_teorica(taxa, 4_000) == (4_000 - fisica, 4_000 + fisica)


def testar_canal_simulado():
    texto = "Mensagem recebida corretamente: acao, fase e modulacao."
    sinal, bits_enviados = psk.criar_audio_da_mensagem(
        texto, taxa_bits=100, portadora=4_001
    )

    # Simula som falso antes da mensagem, diferenca de frequencia entre placas
    # de som, atraso, atenuacao e ruido do ambiente.
    rng = np.random.default_rng(8)
    tempo = np.arange(psk.TAXA_AMOSTRAGEM) / psk.TAXA_AMOSTRAGEM
    interferencia = 0.08 * np.cos(2 * np.pi * 4_000 * tempo)
    interferencia += rng.normal(0, 0.015, len(interferencia))
    atraso = np.zeros(12_345)
    recebido = np.concatenate([interferencia, atraso, 0.45 * sinal])
    recebido += rng.normal(0, 0.008, len(recebido))

    recuperado, bits_recebidos, diagnostico = psk.demodular_bpsk(
        recebido, taxa_bits=100, portadora=4_000
    )
    assert recuperado == texto
    assert diagnostico["metrica_sincronizacao"] > 0.6
    assert bits_recebidos[:len(bits_enviados)] == bits_enviados


def testar_taxas_e_portadoras():
    texto = "Teste"
    for taxa in [50, 100, 200]:
        for portadora in [2_500, 4_000, 5_500]:
            sinal, _ = psk.criar_audio_da_mensagem(texto, taxa, portadora)
            recuperado, _, _ = psk.demodular_bpsk(
                sinal, taxa, portadora
            )
            assert recuperado == texto


def testar_gravacao_da_sala():
    """Regressao real: o receptor antigo falhava no marcador deste WAV."""
    caminho = Path(__file__).parent / "tests/fixtures/recepcao_sala.wav"
    sinal = psk.carregar_wav(caminho)
    texto, _, diagnostico = psk.demodular_bpsk(sinal, 100, 4_000)
    assert texto == "porra "
    assert diagnostico["checksum_valido"]
    assert diagnostico["modo"] == "equalizado"
    assert diagnostico["formato"] == "anterior"
    assert diagnostico["taxa_fisica_bps"] == 100
    assert abs(diagnostico["taxa_util_bps"] - 100 / 3) < 1e-12


def testar_formato_antigo():
    texto = "Gravacao da primeira versao"
    dados = texto.encode("utf-8")
    bits = (psk.PREAMBULO_ANTIGO + psk.MARCADOR_ANTIGO
            + psk.inteiro_para_bits(len(dados), 16)
            + psk.bytes_para_bits(dados)
            + psk.inteiro_para_bits(sum(dados) % 256, 8))
    sinal = psk.adicionar_silencios(psk.modular_bpsk(bits, 100, 4_000))
    recuperado, _, diagnostico = psk.demodular_bpsk(sinal, 100, 4_000)
    assert recuperado == texto
    assert diagnostico["formato"] == "antigo"


def testar_fase_e_relogios():
    texto = "Acao, acentuação e sincronização: " * 3
    for desvio in [-6, 6, 1.017]:
        sinal, _ = psk.criar_audio_da_mensagem(texto, 100, 4_000 + desvio)
        assert psk.demodular_bpsk(sinal, 100, 4_000)[0] == texto

    texto = "Mensagem por duas placas de som."
    sinal, _ = psk.criar_audio_da_mensagem(texto, 100, 4_000)
    for ppm in [-600, 600]:
        fator = 1 + ppm * 1e-6
        posicoes = np.arange(int(len(sinal) / fator)) * fator
        recebido = np.interp(posicoes, np.arange(len(sinal)), sinal)
        assert psk.demodular_bpsk(recebido, 100, 4_000)[0] == texto


def testar_ecos_e_transitorio():
    texto = "Mensagem com ecos"
    sinal, _ = psk.criar_audio_da_mensagem(texto, 100, 4_000)
    recebido = np.pad(sinal, (0, 2_400))
    for atraso, ganho in [(620, 0.8), (1_200, -0.6), (2_100, 0.4)]:
        recebido[atraso:atraso + len(sinal)] += ganho * sinal
    # Um clique anterior muito mais forte nao pode tomar o lugar do quadro.
    recebido[300:312] += 20 * np.cos(2 * np.pi * 4_000 * np.arange(12) / 48_000)
    assert psk.demodular_bpsk(recebido, 100, 4_000)[0] == texto

    # Dois caminhos fortes misturam os novos simbolos de 300 bits/s. Esta
    # mensagem exige o equalizador, alem da regressao do WAV antigo da sala.
    texto = "Teste de equalizacao em 100 bits uteis por segundo"
    sinal, _ = psk.criar_audio_da_mensagem(texto, 100, 4_000)
    recebido = np.pad(sinal, (0, 2_400))
    for atraso in [240, 480]:
        recebido[atraso:atraso + len(sinal)] += 0.9 * sinal
    recuperado, _, diagnostico = psk.demodular_bpsk(recebido, 100, 4_000)
    assert recuperado == texto
    assert diagnostico["modo"] == "equalizado"
    assert diagnostico["taxa_util_bps"] == 100
    assert diagnostico["taxa_fisica_bps"] == 300


def exigir_falha(sinal):
    try:
        psk.demodular_bpsk(sinal, 100, 4_000)
    except ValueError:
        return
    raise AssertionError("O receptor aceitou uma gravacao sem quadro valido")


def testar_rejeicao_de_sinais_invalidos():
    rng = np.random.default_rng(22)
    exigir_falha(np.zeros(3 * psk.TAXA_AMOSTRAGEM))
    exigir_falha(np.array([]))
    exigir_falha(np.array([np.nan]))
    tempo = np.arange(3 * psk.TAXA_AMOSTRAGEM) / psk.TAXA_AMOSTRAGEM
    exigir_falha(np.cos(2 * np.pi * 4_000 * tempo))
    for _ in range(8):
        exigir_falha(rng.normal(0, 0.02, len(tempo)))

    bits = psk.montar_quadro("Checksum detecta o erro")
    inicio_texto = len(psk.PREAMBULO) + len(psk.MARCADOR) + 16 * psk.REPETICOES
    # Inverte um bit logico inteiro: a maioria nao deve ocultar erro no checksum.
    for i in range(inicio_texto, inicio_texto + psk.REPETICOES):
        bits[i] ^= 1
    exigir_falha(psk.adicionar_silencios(psk.modular_bpsk(bits, 300, 4_000)))
    sinal, _ = psk.criar_audio_da_mensagem("Mensagem cortada ao meio", 100, 4_000)
    exigir_falha(sinal[:len(sinal) // 2])


def testar_preservacao_de_tentativa_com_falha():
    # Verifica especificamente o bug da FFT antiga e a preservacao das capturas.
    def fft_de_teste(sinal, titulo, caminho, *args, **kwargs):
        Path(caminho).write_bytes(b"FFT desta tentativa")

    with tempfile.TemporaryDirectory() as pasta:
        raiz = Path(pasta)
        graficos = raiz / "graficos"
        graficos.mkdir()
        (graficos / "02_fft_recebido.png").write_bytes(b"FFT antiga")
        with (patch.object(psk, "PASTA_RESULTADOS", raiz),
              patch.object(psk, "PASTA_GRAFICOS", graficos),
              patch.object(psk, "ARQUIVO_RECEBIDO", raiz / "audio_recebido.wav"),
              patch.object(psk, "gravar", return_value=np.zeros(144_000)),
              patch.object(psk, "plotar_fft", side_effect=fft_de_teste),
              patch("builtins.input", side_effect=["3", ""]),
              patch("builtins.print")):
            try:
                psk.receber(100, 4_000)
            except ValueError:
                pass
            else:
                raise AssertionError("Silencio foi aceito")
        assert (graficos / "02_fft_recebido.png").read_bytes() == b"FFT desta tentativa"
        capturas = list((raiz / "capturas").iterdir())
        assert len(capturas) == 1
        assert (capturas[0] / "audio_recebido.wav").exists()
        import json
        diagnostico = json.loads((capturas[0] / "diagnostico.json").read_text(encoding="utf-8"))
        assert diagnostico["sucesso"] is False
        assert "erro" in diagnostico


if __name__ == "__main__":
    testar_conversoes()
    print("[OK] Conversao de texto, bytes e bits")
    testar_taxa_util_e_duracao()
    print("[OK] 100 bits UTEIS/s, repeticao 3x, duracoes e banda fisica")
    testar_canal_simulado()
    print("[OK] Modulacao e demodulacao com atraso, atenuacao e ruido")
    testar_taxas_e_portadoras()
    print("[OK] Taxas e portadoras alternativas")
    testar_gravacao_da_sala()
    print("[OK] Gravacao real da sala: mensagem e checksum recuperados")
    testar_formato_antigo()
    print("[OK] Compatibilidade com gravacoes da primeira versao")
    testar_fase_e_relogios()
    print("[OK] Mensagens longas, desvio de frequencia e relogios de audio")
    testar_ecos_e_transitorio()
    print("[OK] Ecos e transitorio mais forte que a mensagem")
    testar_rejeicao_de_sinais_invalidos()
    print("[OK] Rejeicao de ruido, silencio, tom, checksum errado e audio cortado")
    testar_preservacao_de_tentativa_com_falha()
    print("[OK] Audio, FFT e diagnostico preservados mesmo quando ha falha")
    print("Todos os testes da Parte 2 passaram.")
