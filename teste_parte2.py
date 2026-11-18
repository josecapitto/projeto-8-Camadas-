"""Testes automaticos da Parte 2 sem microfone e sem alto-falante."""

import numpy as np

import parte2_psk as psk


def testar_conversoes():
    texto = "Ola, engenharia! PSK numero 8."
    quadro = psk.montar_quadro(texto)
    recuperado, usados = psk.interpretar_quadro(quadro)
    assert recuperado == texto
    assert usados == len(quadro)


def testar_canal_simulado():
    texto = "Mensagem recebida corretamente: acao, fase e modulacao."
    sinal, bits_enviados = psk.criar_audio_da_mensagem(
        texto, taxa_bits=100, portadora=4_000
    )

    # Simula atraso entre computadores, atenuacao e ruido do ambiente.
    rng = np.random.default_rng(8)
    atraso = np.zeros(12_345)
    recebido = np.concatenate([atraso, 0.45 * sinal])
    recebido += rng.normal(0, 0.008, len(recebido))

    recuperado, bits_recebidos, diagnostico = psk.demodular_bpsk(
        recebido, taxa_bits=100, portadora=4_000
    )
    assert recuperado == texto
    assert diagnostico["metrica_sincronizacao"] > 0.8
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


if __name__ == "__main__":
    testar_conversoes()
    print("[OK] Conversao de texto, bytes e bits")
    testar_canal_simulado()
    print("[OK] Modulacao e demodulacao com atraso, atenuacao e ruido")
    testar_taxas_e_portadoras()
    print("[OK] Taxas e portadoras alternativas")
    print("Todos os testes da Parte 2 passaram.")
