"""Projeto 8 - Parte 1: simulacao didatica de tres estacoes de radio AM.

O programa faz as duas pontas do sistema:

Emissor: audio -> filtro passa-baixa -> modulacao AM -> soma dos canais.
Receptor: soma -> filtro passa-faixa -> demodulacao -> audio recuperado.

A implementacao foi mantida propositalmente simples. Os filtros sao FIR feitos
com as equacoes vistas em Processamento de Sinais, e a modulacao e apenas uma
multiplicacao ponto a ponto.
"""

from pathlib import Path
import wave

import numpy as np


# ---------------------------------------------------------------------------
# 1. Parametros do projeto
# ---------------------------------------------------------------------------

TAXA_AMOSTRAGEM = 44_100
DURACAO_GRAVACAO = 5  # segundos

# Cada tupla contem: limite inferior, limite superior e portadora.
FAIXAS = [
    (9_000, 12_000, 10_500),
    (12_000, 15_000, 13_500),
    (15_000, 18_000, 16_500),
]

# A metade de cada faixa mede 1500 Hz. Usamos somente 1300 Hz do audio para
# deixar 200 Hz de margem em cada borda da faixa.
CORTE_AUDIO = 1_300

# Quanto maior, mais seletivo e mais lento fica o filtro. Um numero impar
# mantem o filtro simetrico.
TAMANHO_FILTRO = 801

PASTA_ORIGINAIS = Path("audios/originais")
PASTA_RESULTADOS = Path("audios/resultados")
PASTA_GRAFICOS = Path("graficos")
ARQUIVO_DADOS = PASTA_RESULTADOS / "dados_processamento.npz"


def preparar_pastas():
    """Cria as pastas do projeto caso ainda nao existam."""
    PASTA_ORIGINAIS.mkdir(parents=True, exist_ok=True)
    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    PASTA_GRAFICOS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 2. Leitura, gravacao e reproducao de audio
# ---------------------------------------------------------------------------

def normalizar(sinal, pico=0.95):
    """Ajusta o maior valor do sinal para evitar audio estourado."""
    sinal = np.asarray(sinal, dtype=np.float64)
    maior_valor = np.max(np.abs(sinal)) if len(sinal) else 0.0
    if maior_valor == 0:
        return sinal.copy()
    return sinal * (pico / maior_valor)


def salvar_wav(caminho, sinal):
    """Salva um vetor numerico como WAV mono de 16 bits."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    sinal_16_bits = (normalizar(sinal) * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)  # 2 bytes = 16 bits
        arquivo.setframerate(TAXA_AMOSTRAGEM)
        arquivo.writeframes(sinal_16_bits.tobytes())


def reamostrar(sinal, taxa_origem, taxa_destino=TAXA_AMOSTRAGEM):
    """Converte a taxa por FFT, preservando duracao e removendo aliasing.

    Reduzir a taxa corta as frequencias acima do novo limite de Nyquist.
    Isso permite aproveitar os WAVs antigos de 48 kHz sem alterar seu tom
    ou apenas trocar o cabecalho do arquivo.
    """
    sinal = np.asarray(sinal, dtype=np.float64)
    if taxa_origem <= 0 or taxa_destino <= 0:
        raise ValueError("As taxas de amostragem precisam ser positivas.")
    if not len(sinal) or taxa_origem == taxa_destino:
        return sinal.copy()
    tamanho = max(1, round(len(sinal) * taxa_destino / taxa_origem))
    espectro = np.fft.rfft(sinal)
    novo = np.zeros(tamanho // 2 + 1, dtype=complex)
    comum = min(len(sinal), tamanho)
    novo[:comum // 2 + 1] = espectro[:comum // 2 + 1]
    if comum % 2 == 0:
        # O bin de Nyquist representa duas frequencias ao mudar o tamanho.
        if tamanho < len(sinal):
            novo[comum // 2] *= 2
        elif len(sinal) < tamanho:
            novo[comum // 2] *= 0.5
    return np.fft.irfft(novo, n=tamanho) * tamanho / len(sinal)


def carregar_wav(caminho):
    """Le um WAV PCM de 16 bits e devolve amostras entre -1 e 1."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho}")

    with wave.open(str(caminho), "rb") as arquivo:
        canais = arquivo.getnchannels()
        largura = arquivo.getsampwidth()
        taxa = arquivo.getframerate()
        quadros = arquivo.readframes(arquivo.getnframes())

    if largura != 2:
        raise ValueError(f"{caminho} precisa ser um WAV PCM de 16 bits.")

    sinal = np.frombuffer(quadros, dtype=np.int16).astype(np.float64) / 32768.0

    # Se o arquivo for estereo, fazemos a media dos canais para obter mono.
    if canais > 1:
        sinal = sinal.reshape(-1, canais).mean(axis=1)

    return reamostrar(sinal, taxa)


def obter_sounddevice():
    """Importa a biblioteca de audio somente quando ela for necessaria."""
    try:
        import sounddevice as sd
    except ImportError as erro:
        raise RuntimeError(
            "A biblioteca sounddevice nao esta instalada. "
            "Execute: python -m pip install -r requirements.txt"
        ) from erro
    return sd


def gravar_tres_audios():
    """Grava, um de cada vez, os tres audios pedidos no enunciado."""
    preparar_pastas()
    sd = obter_sounddevice()

    for numero in range(1, 4):
        input(
            f"\nEstacao {numero}: pressione ENTER para iniciar uma gravacao "
            f"de {DURACAO_GRAVACAO} segundos."
        )
        print("Gravando... fale agora.")
        gravacao = sd.rec(
            int(DURACAO_GRAVACAO * TAXA_AMOSTRAGEM),
            samplerate=TAXA_AMOSTRAGEM,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        caminho = PASTA_ORIGINAIS / f"estacao{numero}.wav"
        salvar_wav(caminho, gravacao[:, 0])
        print(f"Gravacao salva em {caminho}")


def tocar_audio(caminho):
    """Executa um arquivo WAV e espera o termino da reproducao."""
    sd = obter_sounddevice()
    sinal = carregar_wav(caminho)
    print(f"Tocando {caminho}...")
    sd.play(sinal.astype(np.float32), TAXA_AMOSTRAGEM)
    sd.wait()


def tocar_conjunto(tipo):
    """Toca os tres originais ou os tres sinais demodulados."""
    if tipo == "originais":
        pasta = PASTA_ORIGINAIS
        sufixo = ""
    else:
        pasta = PASTA_RESULTADOS
        sufixo = "_demodulada"

    for numero in range(1, 4):
        caminho = pasta / f"estacao{numero}{sufixo}.wav"
        tocar_audio(caminho)


# ---------------------------------------------------------------------------
# 3. Filtros digitais FIR
# ---------------------------------------------------------------------------

def filtro_passa_baixa(frequencia_corte, tamanho=TAMANHO_FILTRO):
    """Cria os coeficientes de um filtro FIR passa-baixa.

    np.sinc cria a resposta ideal do filtro. A janela de Hamming suaviza as
    extremidades e reduz as ondulacoes causadas pelo corte do filtro ideal.
    """
    if tamanho % 2 == 0:
        tamanho += 1

    n = np.arange(tamanho) - (tamanho - 1) / 2
    corte_normalizado = frequencia_corte / TAXA_AMOSTRAGEM
    h = 2 * corte_normalizado * np.sinc(2 * corte_normalizado * n)
    h *= np.hamming(tamanho)
    h /= np.sum(h)  # ganho igual a 1 nas baixas frequencias
    return h


def filtro_passa_faixa(frequencia_inicial, frequencia_final,
                       tamanho=TAMANHO_FILTRO):
    """Cria um FIR passa-faixa subtraindo dois passa-baixas ideais."""
    if tamanho % 2 == 0:
        tamanho += 1

    n = np.arange(tamanho) - (tamanho - 1) / 2
    f1 = frequencia_inicial / TAXA_AMOSTRAGEM
    f2 = frequencia_final / TAXA_AMOSTRAGEM

    passa_ate_f2 = 2 * f2 * np.sinc(2 * f2 * n)
    passa_ate_f1 = 2 * f1 * np.sinc(2 * f1 * n)
    h = (passa_ate_f2 - passa_ate_f1) * np.hamming(tamanho)

    # Corrige o ganho na frequencia central do canal.
    centro = (frequencia_inicial + frequencia_final) / 2
    indices = np.arange(tamanho)
    ganho = np.abs(np.sum(h * np.exp(-2j * np.pi * centro * indices /
                                     TAXA_AMOSTRAGEM)))
    h /= ganho
    return h


def aplicar_filtro(sinal, coeficientes):
    """Aplica um filtro por convolucao e preserva o tamanho do sinal."""
    return np.convolve(sinal, coeficientes, mode="same")


# ---------------------------------------------------------------------------
# 4. Emissor e receptor AM
# ---------------------------------------------------------------------------

def igualar_duracoes(sinais):
    """Completa os sinais menores com zeros para que possam ser somados."""
    maior_tamanho = max(len(sinal) for sinal in sinais)
    resultado = []
    for sinal in sinais:
        faltam = maior_tamanho - len(sinal)
        resultado.append(np.pad(sinal, (0, faltam)))
    return resultado


def modular(audio, frequencia_portadora):
    """Faz AM DSB-SC: multiplica o audio por uma senoide portadora."""
    tempo = np.arange(len(audio)) / TAXA_AMOSTRAGEM
    portadora = np.sin(2 * np.pi * frequencia_portadora * tempo)
    return audio * portadora


def demodular(sinal_extraido, frequencia_portadora, filtro_audio):
    """Faz demodulacao sincrona e remove a parcela de alta frequencia."""
    tempo = np.arange(len(sinal_extraido)) / TAXA_AMOSTRAGEM
    portadora_local = np.sin(2 * np.pi * frequencia_portadora * tempo)

    # O fator 2 compensa o fator 1/2 produzido por sen(x)^2.
    produto = 2 * sinal_extraido * portadora_local
    return aplicar_filtro(produto, filtro_audio)


def porcentagem_energia_na_faixa(sinal, inicio, fim):
    """Calcula quanto da energia da FFT ficou dentro da faixa permitida."""
    frequencias = np.fft.rfftfreq(len(sinal), 1 / TAXA_AMOSTRAGEM)
    energia = np.abs(np.fft.rfft(sinal)) ** 2
    dentro = (frequencias >= inicio) & (frequencias <= fim)
    if np.sum(energia) == 0:
        return 0.0
    return 100 * np.sum(energia[dentro]) / np.sum(energia)


def processar_projeto(mostrar_graficos_ao_final=True):
    """Executa toda a simulacao: emissor, meio fisico e receptor."""
    preparar_pastas()

    caminhos = [PASTA_ORIGINAIS / f"estacao{i}.wav" for i in range(1, 4)]
    audios = [carregar_wav(caminho) for caminho in caminhos]
    audios = igualar_duracoes(audios)

    print("\n1) Limitando os audios a 1300 Hz...")
    passa_baixa = filtro_passa_baixa(CORTE_AUDIO)
    audios_filtrados = [
        normalizar(aplicar_filtro(audio, passa_baixa)) for audio in audios
    ]

    print("2) Modulando as tres estacoes...")
    modulados = []
    for i, (audio, faixa) in enumerate(zip(audios_filtrados, FAIXAS), start=1):
        inicio, fim, portadora = faixa
        sinal_modulado = modular(audio, portadora)
        modulados.append(sinal_modulado)
        salvar_wav(PASTA_RESULTADOS / f"estacao{i}_modulada.wav",
                    sinal_modulado)

        percentual = porcentagem_energia_na_faixa(
            sinal_modulado, inicio, fim
        )
        situacao = "OK" if percentual >= 99.9 else "ATENCAO"
        print(
            f"   Estacao {i}: {percentual:.5f}% da energia entre "
            f"{inicio / 1000:.0f} e {fim / 1000:.0f} kHz [{situacao}]"
        )

    print("3) Somando os canais para simular o meio fisico...")
    # A divisao por 3 impede que a soma ultrapasse o intervalo [-1, 1].
    meio_fisico = np.sum(modulados, axis=0) / 3
    salvar_wav(PASTA_RESULTADOS / "meio_fisico.wav", meio_fisico)

    print("4) Separando as estacoes com filtros passa-faixa...")
    extraidos = []
    demodulados = []
    for i, faixa in enumerate(FAIXAS, start=1):
        inicio, fim, portadora = faixa
        passa_faixa = filtro_passa_faixa(inicio, fim)
        extraido = aplicar_filtro(meio_fisico, passa_faixa)
        recuperado = demodular(extraido, portadora, passa_baixa)

        extraidos.append(extraido)
        demodulados.append(recuperado)
        salvar_wav(PASTA_RESULTADOS / f"estacao{i}_extraida.wav", extraido)
        salvar_wav(PASTA_RESULTADOS / f"estacao{i}_demodulada.wav", recuperado)

    # Guardamos os vetores para reabrir os graficos sem refazer os calculos.
    np.savez_compressed(
        ARQUIVO_DADOS,
        taxa_amostragem=TAXA_AMOSTRAGEM,
        modulados=np.asarray(modulados),
        meio_fisico=meio_fisico,
        extraidos=np.asarray(extraidos),
    )

    print("5) Gerando os graficos FFT...")
    gerar_graficos(modulados, meio_fisico, extraidos,
                   mostrar=mostrar_graficos_ao_final)

    print("\nProcessamento concluido.")
    print(f"Audios recuperados: {PASTA_RESULTADOS.resolve()}")
    print(f"Graficos: {PASTA_GRAFICOS.resolve()}")


# ---------------------------------------------------------------------------
# 5. Graficos da FFT
# ---------------------------------------------------------------------------

def obter_matplotlib():
    """Importa o Matplotlib somente quando os graficos forem solicitados."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as erro:
        raise RuntimeError(
            "A biblioteca matplotlib nao esta instalada. "
            "Execute: python -m pip install -r requirements.txt"
        ) from erro
    return plt


def calcular_fft_db(sinal):
    """Retorna a FFT em decibeis, normalizada para ter pico em 0 dB."""
    sinal = np.asarray(sinal)
    sinal = sinal - np.mean(sinal)
    janela = np.hanning(len(sinal))
    magnitude = np.abs(np.fft.rfft(sinal * janela))
    magnitude /= np.max(magnitude) + 1e-15
    magnitude_db = 20 * np.log10(magnitude + 1e-12)
    frequencias = np.fft.rfftfreq(len(sinal), 1 / TAXA_AMOSTRAGEM)
    return frequencias, magnitude_db


def configurar_eixo_fft(eixo, titulo, faixa=None):
    """Aplica a mesma aparencia a todos os graficos de espectro."""
    eixo.set_title(titulo)
    eixo.set_xlim(0, TAXA_AMOSTRAGEM / 2)
    eixo.set_ylim(-100, 5)
    eixo.set_xlabel("Frequencia (Hz)")
    eixo.set_ylabel("Magnitude (dB)")
    eixo.grid(True, alpha=0.25)

    if faixa is not None:
        inicio, fim, _ = faixa
        eixo.axvspan(inicio, fim, color="green", alpha=0.12,
                     label="faixa permitida")
        eixo.axvline(inicio, color="green", linestyle="--", linewidth=0.8)
        eixo.axvline(fim, color="green", linestyle="--", linewidth=0.8)
        eixo.legend(loc="lower right")


def gerar_graficos(modulados, meio_fisico, extraidos, mostrar=True):
    """Gera exatamente os tres conjuntos de FFT pedidos no enunciado."""
    preparar_pastas()
    plt = obter_matplotlib()

    # Grafico 1: FFT dos tres audios modulados.
    figura1, eixos1 = plt.subplots(3, 1, figsize=(11, 9), constrained_layout=True)
    for i, (eixo, sinal, faixa) in enumerate(
            zip(eixos1, modulados, FAIXAS), start=1):
        f, db = calcular_fft_db(sinal)
        eixo.plot(f, db, linewidth=0.8)
        configurar_eixo_fft(eixo, f"Estacao {i} modulada", faixa)
    figura1.suptitle("FFT dos tres sinais modulados", fontsize=15)
    figura1.savefig(PASTA_GRAFICOS / "01_fft_modulados.png", dpi=160)

    # Grafico 2: FFT da soma presente no meio fisico.
    figura2, eixo2 = plt.subplots(figsize=(11, 5), constrained_layout=True)
    f, db = calcular_fft_db(meio_fisico)
    eixo2.plot(f, db, linewidth=0.8)
    configurar_eixo_fft(eixo2, "Soma das tres estacoes no meio fisico")
    for inicio, fim, _ in FAIXAS:
        eixo2.axvspan(inicio, fim, alpha=0.08)
        eixo2.axvline(inicio, color="gray", linestyle="--", linewidth=0.7)
    eixo2.axvline(FAIXAS[-1][1], color="gray", linestyle="--", linewidth=0.7)
    figura2.savefig(PASTA_GRAFICOS / "02_fft_meio_fisico.png", dpi=160)

    # Grafico 3: FFT dos canais que o receptor separou.
    figura3, eixos3 = plt.subplots(3, 1, figsize=(11, 9), constrained_layout=True)
    for i, (eixo, sinal, faixa) in enumerate(
            zip(eixos3, extraidos, FAIXAS), start=1):
        f, db = calcular_fft_db(sinal)
        eixo.plot(f, db, linewidth=0.8)
        configurar_eixo_fft(eixo, f"Estacao {i} extraida no receptor", faixa)
    figura3.suptitle("FFT dos sinais separados pelos filtros", fontsize=15)
    figura3.savefig(PASTA_GRAFICOS / "03_fft_extraidos.png", dpi=160)

    if mostrar:
        plt.show()
    else:
        plt.close("all")


def mostrar_graficos_salvos():
    """Reconstroi as figuras a partir do ultimo processamento."""
    if not ARQUIVO_DADOS.exists():
        raise FileNotFoundError(
            "Ainda nao ha resultados. Use primeiro a opcao de processar."
        )
    with np.load(ARQUIVO_DADOS) as dados:
        if "taxa_amostragem" in dados and int(dados["taxa_amostragem"]) == TAXA_AMOSTRAGEM:
            gerar_graficos(dados["modulados"], dados["meio_fisico"], dados["extraidos"], mostrar=True)
            return
    print("Atualizando os resultados antigos para 44100 Hz...")
    processar_projeto(mostrar_graficos_ao_final=True)


# ---------------------------------------------------------------------------
# 6. Menu da aplicacao
# ---------------------------------------------------------------------------

def menu():
    preparar_pastas()

    while True:
        print("\n" + "=" * 62)
        print("PROJETO 8 - PARTE 1 - TRES ESTACOES AM")
        print("=" * 62)
        print("1 - Gravar os 3 audios originais")
        print("2 - Executar os 3 audios originais")
        print("3 - Modular, somar, separar e demodular")
        print("4 - Mostrar novamente os graficos FFT")
        print("5 - Executar os 3 audios demodulados")
        print("0 - Sair")

        escolha = input("Escolha uma opcao: ").strip()

        try:
            if escolha == "1":
                gravar_tres_audios()
            elif escolha == "2":
                tocar_conjunto("originais")
            elif escolha == "3":
                processar_projeto(mostrar_graficos_ao_final=True)
            elif escolha == "4":
                mostrar_graficos_salvos()
            elif escolha == "5":
                tocar_conjunto("demodulados")
            elif escolha == "0":
                print("Programa encerrado.")
                break
            else:
                print("Opcao invalida.")
        except (FileNotFoundError, ValueError, RuntimeError) as erro:
            print(f"\nERRO: {erro}")


if __name__ == "__main__":
    menu()
