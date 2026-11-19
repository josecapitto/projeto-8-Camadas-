"""Projeto 8 - Parte 2: chat didatico usando modulacao digital BPSK.

O mesmo programa pode ser executado nos dois computadores:

- computador emissor: transforma texto em bits e toca um audio BPSK;
- computador receptor: grava o audio, recupera os bits e mostra o texto.

A implementacao privilegia clareza. Nao tenta reproduzir todos os recursos de
um modem comercial; usa somente enquadramento, sincronizacao, BPSK coerente e
uma soma de verificacao simples.
"""

from pathlib import Path
import wave

import numpy as np


# ---------------------------------------------------------------------------
# 1. Parametros faceis de modificar durante a apresentacao
# ---------------------------------------------------------------------------

TAXA_AMOSTRAGEM = 48_000
TAXA_BITS_PADRAO = 100          # requisito do enunciado: 100 bits/s
PORTADORA_PADRAO = 4_000        # deve ficar entre 2 kHz e 6 kHz
AMPLITUDE = 0.75
SILENCIO_INICIAL = 0.8          # ajuda o receptor a encontrar o inicio
SILENCIO_FINAL = 0.5

# Alternancia conhecida usada pelo receptor para descobrir inicio e fase.
# Um preambulo maior torna a busca mais segura em gravacoes com ruido.
PREAMBULO = [1, 0] * 32

# Palavra conhecida que confirma que o quadro realmente comecou ali.
MARCADOR = [int(bit) for bit in f"{0xDDAA96B5:032b}"]

# Cada bit de cabecalho, texto e checksum e enviado tres vezes. O receptor
# decide por maioria. A portadora continua mudando a 100 bits/s; apenas a taxa
# de informacao util fica menor em troca de maior resistencia a erros.
REPETICOES = 3
MAXIMO_BYTES = 512

PASTA_RESULTADOS = Path("parte2/resultados")
PASTA_GRAFICOS = Path("parte2/graficos")
ARQUIVO_EMITIDO = PASTA_RESULTADOS / "audio_emitido.wav"
ARQUIVO_RECEBIDO = PASTA_RESULTADOS / "audio_recebido.wav"


def preparar_pastas():
    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    PASTA_GRAFICOS.mkdir(parents=True, exist_ok=True)


def validar_parametros(taxa_bits, portadora):
    if taxa_bits <= 0:
        raise ValueError("A taxa de bits precisa ser positiva.")
    if not 2_000 <= portadora <= 6_000:
        raise ValueError("A portadora precisa estar entre 2000 e 6000 Hz.")
    if TAXA_AMOSTRAGEM % taxa_bits != 0:
        raise ValueError(
            f"Escolha uma taxa que divida {TAXA_AMOSTRAGEM}. "
            "Exemplos: 50, 100, 200 ou 400 bits/s."
        )


# ---------------------------------------------------------------------------
# 2. Conversao texto <-> bits e construcao do quadro
# ---------------------------------------------------------------------------

def inteiro_para_bits(valor, quantidade):
    """Converte um inteiro em uma lista de bits, do mais significativo ao menor."""
    return [int(bit) for bit in f"{valor:0{quantidade}b}"]


def bits_para_inteiro(bits):
    """Faz a operacao inversa de inteiro_para_bits."""
    return int("".join(str(bit) for bit in bits), 2)


def bytes_para_bits(dados):
    bits = []
    for byte in dados:
        bits.extend(inteiro_para_bits(byte, 8))
    return bits


def bits_para_bytes(bits):
    if len(bits) % 8 != 0:
        raise ValueError("A quantidade de bits do texto nao e multipla de 8.")
    return bytes(
        bits_para_inteiro(bits[i:i + 8])
        for i in range(0, len(bits), 8)
    )


def codificar_repeticao(bits):
    """Repete cada bit para permitir decisao por maioria no receptor."""
    return [bit for bit in bits for _ in range(REPETICOES)]


def decodificar_repeticao(bits):
    """Recupera um bit a cada grupo, escolhendo o valor majoritario."""
    quantidade = len(bits) // REPETICOES
    resultado = []
    for i in range(quantidade):
        grupo = bits[i * REPETICOES:(i + 1) * REPETICOES]
        resultado.append(1 if sum(grupo) > REPETICOES // 2 else 0)
    return resultado


def montar_quadro(texto):
    """Monta o quadro BPSK com redundancia nos campos de dados."""
    dados = texto.encode("utf-8")
    if not dados:
        raise ValueError("Digite uma mensagem antes de transmitir.")
    if len(dados) > MAXIMO_BYTES:
        raise ValueError(f"Use no maximo {MAXIMO_BYTES} bytes por mensagem.")

    tamanho = inteiro_para_bits(len(dados), 16)
    conteudo = bytes_para_bits(dados)
    checksum = inteiro_para_bits(sum(dados) % 256, 8)
    protegidos = codificar_repeticao(tamanho + conteudo + checksum)
    return PREAMBULO + MARCADOR + protegidos


def interpretar_quadro(bits):
    """Remove a redundancia, valida o quadro e reconstrói o texto."""
    inicio_marcador = len(PREAMBULO)
    fim_marcador = inicio_marcador + len(MARCADOR)
    marcador_recebido = bits[inicio_marcador:fim_marcador]
    erros_marcador = sum(
        recebido != esperado
        for recebido, esperado in zip(marcador_recebido, MARCADOR)
    )
    if len(marcador_recebido) != len(MARCADOR) or erros_marcador > 3:
        raise ValueError(
            "Marcador nao encontrado. A gravacao pode estar baixa, ruidosa "
            "ou com a portadora incorreta."
        )

    bits_protegidos = bits[fim_marcador:]
    tamanho_protegido = 16 * REPETICOES
    if len(bits_protegidos) < tamanho_protegido:
        raise ValueError("A gravacao terminou antes do cabecalho.")

    cabecalho = decodificar_repeticao(
        bits_protegidos[:tamanho_protegido]
    )
    quantidade_bytes = bits_para_inteiro(cabecalho[:16])
    if quantidade_bytes > MAXIMO_BYTES:
        raise ValueError(
            "Cabecalho corrompido: o tamanho recebido nao e valido. "
            "Reduza o ruido ou aproxime os computadores."
        )

    quantidade_logica = 16 + quantidade_bytes * 8 + 8
    quantidade_fisica = quantidade_logica * REPETICOES
    if len(bits_protegidos) < quantidade_fisica:
        raise ValueError(
            "A gravacao terminou antes do final da mensagem. "
            "Aumente o tempo de gravacao do receptor."
        )

    logicos = decodificar_repeticao(
        bits_protegidos[:quantidade_fisica]
    )
    inicio_texto = 16
    fim_texto = inicio_texto + quantidade_bytes * 8
    fim_checksum = fim_texto + 8
    dados = bits_para_bytes(logicos[inicio_texto:fim_texto])
    checksum_recebido = bits_para_inteiro(logicos[fim_texto:fim_checksum])
    checksum_calculado = sum(dados) % 256
    if checksum_recebido != checksum_calculado:
        raise ValueError(
            "Checksum incorreto: algum bit foi recebido errado. "
            "Aproxime o microfone, ajuste o volume ou reduza o ruido."
        )

    try:
        usados = fim_marcador + quantidade_fisica
        return dados.decode("utf-8"), usados
    except UnicodeDecodeError as erro:
        raise ValueError("Os bytes recebidos nao formam um texto UTF-8.") from erro


# ---------------------------------------------------------------------------
# 3. Modulacao BPSK
# ---------------------------------------------------------------------------

def modular_bpsk(bits, taxa_bits, portadora):
    """Converte bits em fases: bit 1 = 0 graus; bit 0 = 180 graus."""
    validar_parametros(taxa_bits, portadora)
    amostras_por_bit = TAXA_AMOSTRAGEM // taxa_bits

    # +1 representa fase 0; -1 representa uma inversao de 180 graus.
    simbolos = np.where(np.asarray(bits) == 1, 1.0, -1.0)
    simbolos_amostrados = np.repeat(simbolos, amostras_por_bit)

    tempo = np.arange(len(simbolos_amostrados)) / TAXA_AMOSTRAGEM
    portadora_senoidal = np.cos(2 * np.pi * portadora * tempo)
    sinal = AMPLITUDE * simbolos_amostrados * portadora_senoidal
    return sinal


def adicionar_silencios(sinal):
    antes = np.zeros(round(SILENCIO_INICIAL * TAXA_AMOSTRAGEM))
    depois = np.zeros(round(SILENCIO_FINAL * TAXA_AMOSTRAGEM))
    return np.concatenate([antes, sinal, depois])


def criar_audio_da_mensagem(texto, taxa_bits, portadora):
    bits = montar_quadro(texto)
    modulado = modular_bpsk(bits, taxa_bits, portadora)
    return adicionar_silencios(modulado), bits


# ---------------------------------------------------------------------------
# 4. Sincronizacao e demodulacao
# ---------------------------------------------------------------------------

def energia_movel(sinal, janela):
    """Calcula energia media sem usar bibliotecas avancadas de sinais."""
    energia = np.asarray(sinal, dtype=np.float64) ** 2
    acumulada = np.concatenate([[0.0], np.cumsum(energia)])
    if len(energia) < janela:
        return np.array([])
    return (acumulada[janela:] - acumulada[:-janela]) / janela


def estimar_inicio(sinal, amostras_por_bit):
    """Procura onde a energia deixa de ser silencio e passa a ser BPSK."""
    energias = energia_movel(sinal, max(16, amostras_por_bit // 2))
    if len(energias) == 0:
        raise ValueError("Gravacao curta demais.")

    piso = np.percentile(energias, 20)
    pico = np.percentile(energias, 99)
    if pico < max(1e-8, piso * 3):
        raise ValueError("Nenhum sinal PSK foi detectado na gravacao.")

    limite = piso + 0.20 * (pico - piso)
    encontrados = np.flatnonzero(energias > limite)
    if len(encontrados) == 0:
        raise ValueError("Nao foi possivel localizar o inicio do audio.")
    return int(encontrados[0])


def filtrar_em_torno_da_portadora(sinal, taxa_bits, portadora):
    """Remove sons distantes da portadora antes da sincronizacao.

    O filtro e aplicado no dominio da frequencia porque o receptor trabalha
    com a gravacao completa. A transicao suave evita um corte muito abrupto.
    """
    sinal = np.asarray(sinal, dtype=np.float64)
    frequencias = np.fft.rfftfreq(len(sinal), 1 / TAXA_AMOSTRAGEM)
    espectro = np.fft.rfft(sinal)
    distancia = np.abs(frequencias - portadora)
    largura = max(600.0, 4.0 * taxa_bits)
    transicao = 250.0

    mascara = np.zeros_like(frequencias)
    mascara[distancia <= largura] = 1.0
    zona = (distancia > largura) & (distancia < largura + transicao)
    mascara[zona] = 0.5 * (
        1 + np.cos(np.pi * (distancia[zona] - largura) / transicao)
    )
    return np.fft.irfft(espectro * mascara, n=len(sinal))


def integra_simbolos(acumulada_complexa, inicio, quantidade, amostras_por_bit):
    """Integra cada intervalo de bit depois da mistura com a portadora local."""
    comecos = inicio + np.arange(quantidade) * amostras_por_bit
    finais = comecos + amostras_por_bit
    if finais[-1] >= len(acumulada_complexa):
        return None
    return acumulada_complexa[finais] - acumulada_complexa[comecos]


def sincronizar(sinal, taxa_bits, portadora):
    """Busca o preambulo na gravacao inteira e estima fase e deriva."""
    validar_parametros(taxa_bits, portadora)
    amostras_por_bit = TAXA_AMOSTRAGEM // taxa_bits
    sinal_filtrado = filtrar_em_torno_da_portadora(
        sinal, taxa_bits, portadora
    )

    n = np.arange(len(sinal_filtrado))
    oscilador_complexo = np.exp(-2j * np.pi * portadora * n /
                                TAXA_AMOSTRAGEM)
    misturado = sinal_filtrado * oscilador_complexo
    acumulada = np.concatenate([[0j], np.cumsum(misturado)])

    conhecidos = np.asarray(
        [1.0 if bit == 1 else -1.0 for bit in PREAMBULO + MARCADOR]
    )
    quantidade_conhecida = len(conhecidos)

    ultimo = len(sinal_filtrado) - quantidade_conhecida * amostras_por_bit - 1
    if ultimo <= 0:
        raise ValueError("Nao ha amostras suficientes para sincronizar.")

    def avaliar(candidato):
        simbolos = integra_simbolos(
            acumulada, candidato, quantidade_conhecida, amostras_por_bit
        )
        if simbolos is None:
            return None
        produtos = simbolos * conhecidos

        # Soma a correlacao em blocos curtos e depois combina os modulos. Isso
        # tolera uma lenta rotacao de fase, mas rejeita um tom continuo: no tom
        # sem dados, os sinais +1/-1 conhecidos se cancelam dentro dos blocos.
        tamanho_bloco = 8
        somas = [
            np.sum(produtos[i:i + tamanho_bloco])
            for i in range(0, quantidade_conhecida, tamanho_bloco)
        ]
        metrica = np.sum(np.abs(somas)) / (
            np.sum(np.abs(simbolos)) + 1e-15
        )
        correlacao = np.sum(produtos)
        energia = float(np.mean(np.abs(simbolos)))
        return float(metrica), energia, correlacao

    # Busca grosseira em toda a gravacao. Isso evita que um clique ou uma voz
    # antes da mensagem seja confundido com o inicio do quadro.
    passo = max(1, amostras_por_bit // 8)
    candidatos = []
    for candidato in range(0, ultimo + 1, passo):
        avaliacao = avaliar(candidato)
        if avaliacao is not None:
            metrica, energia, correlacao = avaliacao
            candidatos.append((candidato, metrica, energia, correlacao))

    if not candidatos:
        raise ValueError("Nao foi possivel procurar o preambulo.")

    maior_energia = max(item[2] for item in candidatos) + 1e-15
    candidatos = [
        item for item in candidatos
        if item[2] >= 0.05 * maior_energia
    ]

    def pontuacao(item):
        return item[1] * np.sqrt(item[2] / maior_energia)

    grosseiro = max(candidatos, key=pontuacao)

    # Refina amostra por amostra ao redor do melhor ponto grosseiro.
    refinados = []
    primeiro = max(0, grosseiro[0] - passo)
    final = min(ultimo, grosseiro[0] + passo)
    for candidato in range(primeiro, final + 1):
        avaliacao = avaliar(candidato)
        if avaliacao is not None:
            metrica, energia, correlacao = avaliacao
            refinados.append((candidato, metrica, energia, correlacao))

    melhor_inicio, _, _, _ = max(refinados, key=pontuacao)
    simbolos_conhecidos = integra_simbolos(
        acumulada, melhor_inicio, quantidade_conhecida, amostras_por_bit
    )

    # Procura uma pequena rotacao de fase por simbolo. Ela representa a
    # diferenca entre os relogios das duas placas de som.
    indices = np.arange(quantidade_conhecida)
    melhor_metrica = -1.0
    melhor_correlacao = None
    melhor_deriva = 0.0
    for deriva in np.linspace(-0.20, 0.20, 161):
        compensacao = np.exp(-1j * deriva * indices)
        correlacao = np.sum(
            simbolos_conhecidos * conhecidos * compensacao
        )
        metrica = np.abs(correlacao) / (
            np.sum(np.abs(simbolos_conhecidos)) + 1e-15
        )
        if metrica > melhor_metrica:
            melhor_metrica = float(metrica)
            melhor_correlacao = correlacao
            melhor_deriva = float(deriva)

    if melhor_metrica < 0.28:
        raise ValueError(
            "Sincronizacao fraca mesmo apos procurar toda a gravacao. "
            "Confirme o microfone, a taxa e a portadora."
        )

    fase = float(np.angle(melhor_correlacao))
    return (
        melhor_inicio, fase, melhor_deriva, melhor_metrica, acumulada
    )


def demodular_bpsk(sinal, taxa_bits, portadora):
    """Recupera a mensagem usando uma portadora local e decisao pelo sinal."""
    inicio, fase, deriva, metrica, acumulada = sincronizar(
        sinal, taxa_bits, portadora
    )
    amostras_por_bit = TAXA_AMOSTRAGEM // taxa_bits
    quantidade = (len(sinal) - inicio) // amostras_por_bit
    simbolos = integra_simbolos(
        acumulada, inicio, quantidade, amostras_por_bit
    )
    if simbolos is None:
        raise ValueError("Falha ao dividir a gravacao em bits.")

    # Corrige tanto a fase inicial quanto sua lenta variacao ao longo do audio.
    fases = fase + deriva * np.arange(len(simbolos))
    corrigidos = simbolos * np.exp(-1j * fases)
    bits = (np.real(corrigidos) >= 0).astype(int).tolist()
    texto, bits_utilizados = interpretar_quadro(bits)

    diagnostico = {
        "inicio_amostra": inicio,
        "fase_graus": np.degrees(fase),
        "deriva_hz": deriva * taxa_bits / (2 * np.pi),
        "metrica_sincronizacao": metrica,
        "bits_decodificados": bits_utilizados,
    }
    return texto, bits, diagnostico


# ---------------------------------------------------------------------------
# 5. Arquivos WAV, microfone e alto-falante
# ---------------------------------------------------------------------------

def normalizar(sinal, pico=0.95):
    sinal = np.asarray(sinal, dtype=np.float64)
    maior = np.max(np.abs(sinal)) if len(sinal) else 0.0
    return sinal.copy() if maior == 0 else sinal * (pico / maior)


def salvar_wav(caminho, sinal):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    pcm = (normalizar(sinal) * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(TAXA_AMOSTRAGEM)
        arquivo.writeframes(pcm.tobytes())


def carregar_wav(caminho):
    with wave.open(str(caminho), "rb") as arquivo:
        if arquivo.getsampwidth() != 2:
            raise ValueError("O WAV precisa ter 16 bits.")
        if arquivo.getframerate() != TAXA_AMOSTRAGEM:
            raise ValueError(
                f"O WAV precisa estar em {TAXA_AMOSTRAGEM} Hz."
            )
        canais = arquivo.getnchannels()
        dados = arquivo.readframes(arquivo.getnframes())
    sinal = np.frombuffer(dados, dtype=np.int16).astype(np.float64) / 32768
    if canais > 1:
        sinal = sinal.reshape(-1, canais).mean(axis=1)
    return sinal


def obter_sounddevice():
    try:
        import sounddevice as sd
    except ImportError as erro:
        raise RuntimeError(
            "Instale as dependencias com: "
            "python -m pip install -r requirements.txt"
        ) from erro
    return sd


def tocar(sinal):
    sd = obter_sounddevice()
    sd.play(np.asarray(sinal, dtype=np.float32), TAXA_AMOSTRAGEM)
    sd.wait()


def gravar(duracao):
    sd = obter_sounddevice()
    print(f"Gravando por {duracao:.1f} segundos...")
    gravacao = sd.rec(
        round(duracao * TAXA_AMOSTRAGEM),
        samplerate=TAXA_AMOSTRAGEM,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    return gravacao[:, 0].astype(np.float64)


# ---------------------------------------------------------------------------
# 6. FFT, banda e experimentos pedidos no enunciado
# ---------------------------------------------------------------------------

def obter_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ImportError as erro:
        raise RuntimeError(
            "Instale as dependencias com: "
            "python -m pip install -r requirements.txt"
        ) from erro
    return plt


def calcular_fft_db(sinal):
    sinal = np.asarray(sinal, dtype=np.float64)
    sinal = sinal - np.mean(sinal)
    janela = np.hanning(len(sinal))
    magnitude = np.abs(np.fft.rfft(sinal * janela))
    magnitude /= np.max(magnitude) + 1e-15
    db = 20 * np.log10(magnitude + 1e-12)
    frequencias = np.fft.rfftfreq(len(sinal), 1 / TAXA_AMOSTRAGEM)
    return frequencias, db


def banda_teorica(taxa_bits, portadora):
    """Em BPSK retangular, o lobulo principal vai de fc-Rb ate fc+Rb."""
    return portadora - taxa_bits, portadora + taxa_bits


def plotar_fft(sinal, titulo, caminho, taxa_bits, portadora, mostrar=True):
    plt = obter_matplotlib()
    frequencias, db = calcular_fft_db(sinal)
    inferior, superior = banda_teorica(taxa_bits, portadora)

    figura, eixo = plt.subplots(figsize=(11, 5), constrained_layout=True)
    eixo.plot(frequencias, db, linewidth=0.8)
    eixo.axvline(portadora, color="black", linestyle=":",
                 label=f"portadora = {portadora} Hz")
    eixo.axvspan(inferior, superior, color="green", alpha=0.15,
                 label=f"lobulo principal ≈ {2 * taxa_bits} Hz")
    eixo.set_xlim(max(0, portadora - 1_000), portadora + 1_000)
    eixo.set_ylim(-100, 5)
    eixo.set_title(titulo)
    eixo.set_xlabel("Frequencia (Hz)")
    eixo.set_ylabel("Magnitude (dB)")
    eixo.grid(True, alpha=0.25)
    eixo.legend()
    figura.savefig(caminho, dpi=160)
    if mostrar:
        plt.show()
    else:
        plt.close(figura)


def comparar_taxas(texto="TESTE DE TAXA PSK"):
    """Mostra que aumentar bits/s alarga o espectro ao redor da portadora."""
    plt = obter_matplotlib()
    figura, eixo = plt.subplots(figsize=(11, 6), constrained_layout=True)
    portadora = PORTADORA_PADRAO

    for taxa in [50, 100, 200]:
        sinal, _ = criar_audio_da_mensagem(texto, taxa, portadora)
        f, db = calcular_fft_db(sinal)
        mascara = (f >= portadora - 700) & (f <= portadora + 700)
        eixo.plot(f[mascara], db[mascara], linewidth=0.9,
                  label=f"{taxa} bits/s - banda principal ≈ {2*taxa} Hz")

    eixo.axvline(portadora, color="black", linestyle=":")
    eixo.set_title("Efeito da taxa de bits na FFT BPSK")
    eixo.set_xlabel("Frequencia (Hz)")
    eixo.set_ylabel("Magnitude normalizada (dB)")
    eixo.set_ylim(-80, 5)
    eixo.grid(True, alpha=0.25)
    eixo.legend()
    caminho = PASTA_GRAFICOS / "03_comparacao_taxas.png"
    figura.savefig(caminho, dpi=160)
    plt.show()


def comparar_portadoras(texto="TESTE DE PORTADORA PSK"):
    """Mostra que mudar fc desloca o espectro sem mudar sua largura."""
    plt = obter_matplotlib()
    figura, eixo = plt.subplots(figsize=(11, 6), constrained_layout=True)

    for portadora in [2_500, 4_000, 5_500]:
        sinal, _ = criar_audio_da_mensagem(
            texto, TAXA_BITS_PADRAO, portadora
        )
        f, db = calcular_fft_db(sinal)
        mascara = (f >= 1_800) & (f <= 6_200)
        eixo.plot(f[mascara], db[mascara], linewidth=0.8,
                  label=f"portadora = {portadora} Hz")

    eixo.set_title("Efeito da frequencia da portadora na FFT BPSK")
    eixo.set_xlabel("Frequencia (Hz)")
    eixo.set_ylabel("Magnitude normalizada (dB)")
    eixo.set_ylim(-80, 5)
    eixo.grid(True, alpha=0.25)
    eixo.legend()
    caminho = PASTA_GRAFICOS / "04_comparacao_portadoras.png"
    figura.savefig(caminho, dpi=160)
    plt.show()


# ---------------------------------------------------------------------------
# 7. Operacoes do menu
# ---------------------------------------------------------------------------

def imprimir_diagnostico_emissao(texto, bits, sinal, taxa_bits, portadora):
    duracao_bits = len(bits) / taxa_bits
    inferior, superior = banda_teorica(taxa_bits, portadora)
    dados = texto.encode("utf-8")

    print("\n--- DIAGNOSTICO DO EMISSOR ---")
    print(f"Texto: {texto}")
    print(f"Bytes UTF-8: {list(dados)}")
    print(f"Primeiros bits: {''.join(map(str, bits[:96]))}")
    print(f"Total do quadro: {len(bits)} bits")
    print(f"Taxa: {taxa_bits} bits/s")
    print(f"Duracao dos bits: {duracao_bits:.3f} s")
    print(f"Duracao total com silencios: {len(sinal)/TAXA_AMOSTRAGEM:.3f} s")
    print(f"Amostras por bit: {TAXA_AMOSTRAGEM // taxa_bits}")
    print(f"Portadora: {portadora} Hz")
    print(
        f"Lobulo principal: {inferior} a {superior} Hz "
        f"(largura aproximada de {2 * taxa_bits} Hz)"
    )


def transmitir(taxa_bits, portadora):
    texto = input("\nDigite a mensagem e pressione ENTER: ")
    sinal, bits = criar_audio_da_mensagem(texto, taxa_bits, portadora)
    salvar_wav(ARQUIVO_EMITIDO, sinal)
    imprimir_diagnostico_emissao(
        texto, bits, sinal, taxa_bits, portadora
    )
    plotar_fft(
        sinal,
        "FFT do sinal BPSK emitido",
        PASTA_GRAFICOS / "01_fft_emitido.png",
        taxa_bits,
        portadora,
        mostrar=False,
    )
    print("\nTransmitindo pelo alto-falante...")
    tocar(sinal)
    print(f"FFT salva em {PASTA_GRAFICOS / '01_fft_emitido.png'}")


def receber(taxa_bits, portadora):
    entrada = input("Tempo de gravacao em segundos [15]: ").strip()
    duracao = float(entrada) if entrada else 15.0
    if duracao <= 1:
        raise ValueError("Use uma gravacao maior que 1 segundo.")

    input(
        "Pressione ENTER para iniciar; depois transmita no outro computador."
    )
    sinal = gravar(duracao)
    salvar_wav(ARQUIVO_RECEBIDO, sinal)
    texto, bits, diagnostico = demodular_bpsk(
        sinal, taxa_bits, portadora
    )
    plotar_fft(
        sinal,
        "FFT do sinal BPSK recebido",
        PASTA_GRAFICOS / "02_fft_recebido.png",
        taxa_bits,
        portadora,
        mostrar=False,
    )

    print("\n--- DIAGNOSTICO DO RECEPTOR ---")
    print(f"Inicio detectado na amostra: {diagnostico['inicio_amostra']}")
    print(f"Fase estimada: {diagnostico['fase_graus']:.2f} graus")
    print(
        "Diferenca estimada de frequencia: "
        f"{diagnostico['deriva_hz']:.3f} Hz"
    )
    print(
        "Qualidade da sincronizacao: "
        f"{diagnostico['metrica_sincronizacao']:.3f}"
    )
    print(f"Primeiros bits: {''.join(map(str, bits[:96]))}")
    print("\n" + "=" * 62)
    print(f"MENSAGEM RECEBIDA: {texto}")
    print("=" * 62)
    print(f"FFT salva em {PASTA_GRAFICOS / '02_fft_recebido.png'}")


def teste_local(taxa_bits, portadora):
    """Decodifica o ultimo WAV emitido sem alto-falante nem microfone."""
    if not ARQUIVO_EMITIDO.exists():
        texto = input("Digite uma mensagem para o teste local: ")
        sinal, _ = criar_audio_da_mensagem(texto, taxa_bits, portadora)
        salvar_wav(ARQUIVO_EMITIDO, sinal)

    sinal = carregar_wav(ARQUIVO_EMITIDO)
    texto, bits, diagnostico = demodular_bpsk(
        sinal, taxa_bits, portadora
    )
    print("\nTeste local concluido sem usar microfone.")
    print(f"Mensagem recuperada: {texto}")
    print(
        f"Sincronizacao: {diagnostico['metrica_sincronizacao']:.3f}; "
        f"fase: {diagnostico['fase_graus']:.2f} graus"
    )
    print(f"Bits lidos: {len(bits)}")


def ler_inteiro_opcional(pergunta, atual):
    entrada = input(f"{pergunta} [{atual}]: ").strip()
    return atual if not entrada else int(entrada)


def menu():
    preparar_pastas()
    taxa_bits = TAXA_BITS_PADRAO
    portadora = PORTADORA_PADRAO

    while True:
        print("\n" + "=" * 66)
        print("PROJETO 8 - PARTE 2 - CHAT BPSK")
        print(f"Configuracao: {taxa_bits} bits/s | portadora {portadora} Hz")
        print("=" * 66)
        print("1 - EMISSOR: digitar e transmitir uma mensagem")
        print("2 - RECEPTOR: gravar e decodificar uma mensagem")
        print("3 - Teste local do ultimo audio (sem microfone)")
        print("4 - Comparar taxas de 50, 100 e 200 bits/s")
        print("5 - Comparar portadoras de 2,5, 4 e 5,5 kHz")
        print("6 - Alterar taxa de bits e portadora")
        print("7 - Mostrar FFT emitida e recebida")
        print("0 - Sair")

        escolha = input("Escolha: ").strip()
        try:
            if escolha == "1":
                transmitir(taxa_bits, portadora)
            elif escolha == "2":
                receber(taxa_bits, portadora)
            elif escolha == "3":
                teste_local(taxa_bits, portadora)
            elif escolha == "4":
                comparar_taxas()
            elif escolha == "5":
                comparar_portadoras()
            elif escolha == "6":
                nova_taxa = ler_inteiro_opcional(
                    "Nova taxa em bits/s", taxa_bits
                )
                nova_portadora = ler_inteiro_opcional(
                    "Nova portadora em Hz", portadora
                )
                validar_parametros(nova_taxa, nova_portadora)
                taxa_bits, portadora = nova_taxa, nova_portadora
            elif escolha == "7":
                plt = obter_matplotlib()
                arquivos = [
                    PASTA_GRAFICOS / "01_fft_emitido.png",
                    PASTA_GRAFICOS / "02_fft_recebido.png",
                ]
                existentes = [arquivo for arquivo in arquivos if arquivo.exists()]
                if not existentes:
                    raise FileNotFoundError(
                        "Transmita ou receba uma mensagem primeiro."
                    )
                figura, eixos = plt.subplots(
                    len(existentes), 1,
                    figsize=(11, 5 * len(existentes)),
                    constrained_layout=True,
                )
                eixos = np.atleast_1d(eixos)
                for eixo, arquivo in zip(eixos, existentes):
                    eixo.imshow(plt.imread(arquivo))
                    eixo.axis("off")
                    eixo.set_title(arquivo.stem)
                plt.show()
            elif escolha == "0":
                print("Programa encerrado.")
                break
            else:
                print("Opcao invalida.")
        except (FileNotFoundError, RuntimeError, ValueError, wave.Error) as erro:
            print(f"\nERRO: {erro}")


if __name__ == "__main__":
    menu()
