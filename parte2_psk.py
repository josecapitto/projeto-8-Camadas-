"""Projeto 8 - Parte 2: chat didatico usando modulacao digital BPSK.

O mesmo programa pode ser executado nos dois computadores:

- computador emissor: transforma texto em bits e toca um audio BPSK;
- computador receptor: grava o audio, recupera os bits e mostra o texto.

A implementacao privilegia clareza. Nao tenta reproduzir todos os recursos de
um modem comercial; usa somente enquadramento, sincronizacao, BPSK coerente e
uma soma de verificacao simples.
"""

from pathlib import Path
from datetime import datetime
import argparse
import json
import wave

import numpy as np


# ---------------------------------------------------------------------------
# 1. Parametros faceis de modificar durante a apresentacao
# ---------------------------------------------------------------------------

TAXA_AMOSTRAGEM = 48_000
TAXA_BITS_PADRAO = 100          # bits UTEIS/s dos caracteres, antes da repeticao
PORTADORA_PADRAO = 4_000        # deve ficar entre 2 kHz e 6 kHz
AMPLITUDE = 0.75
SILENCIO_INICIAL = 0.8          # ajuda o receptor a encontrar o inicio
SILENCIO_FINAL = 0.5

# Alternancia conhecida usada pelo receptor para descobrir inicio e fase.
# Triplicamos a sequencia conhecida junto com a velocidade fisica: em
# 300 bits/s, o treinamento continua durando 0,96 s como na versao anterior.
PREAMBULO = [1, 0] * 96

# Palavra conhecida que confirma que o quadro realmente comecou ali.
MARCADOR = [int(bit) for bit in f"{0xDDAA96B56E2B4C93A7F019D6:096b}"]

# Cada bit de cabecalho, texto e checksum e enviado tres vezes. O receptor
# decide por maioria. Para 100 bits uteis/s, o modulador envia 300 bits/s.
# Cabecalho, treinamento e silencios sao acrescimos ao tempo dos caracteres.
REPETICOES = 3
MAXIMO_BYTES = 512

# Compatibilidade com o quadro repetido anterior (a gravacao da sala) e com
# a primeira versao, sem repeticao. Nunca alteramos esses WAVs para decodificar.
PREAMBULO_ANTERIOR = [1, 0] * 32
MARCADOR_ANTERIOR = [int(bit) for bit in f"{0xDDAA96B5:032b}"]
PREAMBULO_ANTIGO = [1, 0] * 16
MARCADOR_ANTIGO = [int(bit) for bit in f"{0xDDAA:016b}"]

PASTA_RESULTADOS = Path("parte2/resultados")
PASTA_GRAFICOS = Path("parte2/graficos")
ARQUIVO_EMITIDO = PASTA_RESULTADOS / "audio_emitido.wav"
ARQUIVO_RECEBIDO = PASTA_RESULTADOS / "audio_recebido.wav"


def preparar_pastas():
    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    PASTA_GRAFICOS.mkdir(parents=True, exist_ok=True)


def calcular_taxa_fisica(taxa_util):
    """Cada bit util ocupa tres simbolos BPSK por causa da repeticao."""
    return taxa_util * REPETICOES


def validar_taxa_fisica(taxa_bits, portadora):
    if taxa_bits <= 0:
        raise ValueError("A taxa de bits precisa ser positiva.")
    if not 2_000 <= portadora <= 6_000:
        raise ValueError("A portadora precisa estar entre 2000 e 6000 Hz.")
    if TAXA_AMOSTRAGEM % taxa_bits != 0:
        raise ValueError(
            f"A taxa fisica precisa dividir {TAXA_AMOSTRAGEM}. "
            "Use, por exemplo, 50, 100, 200 ou 400 bits uteis/s."
        )


def validar_parametros(taxa_util, portadora):
    validar_taxa_fisica(calcular_taxa_fisica(taxa_util), portadora)


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


def decodificar_repeticao(bits, repeticoes=REPETICOES):
    """Recupera um bit a cada grupo, escolhendo o valor majoritario."""
    quantidade = len(bits) // repeticoes
    resultado = []
    for i in range(quantidade):
        grupo = bits[i * repeticoes:(i + 1) * repeticoes]
        resultado.append(1 if sum(grupo) > repeticoes // 2 else 0)
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


def parametros_quadro(formato):
    if formato == "atual":
        return PREAMBULO, MARCADOR, REPETICOES
    if formato == "anterior":
        return PREAMBULO_ANTERIOR, MARCADOR_ANTERIOR, REPETICOES
    if formato == "antigo":
        return PREAMBULO_ANTIGO, MARCADOR_ANTIGO, 1
    raise ValueError(f"Formato de quadro desconhecido: {formato}")


def interpretar_quadro(bits, formato="atual"):
    """Remove a redundancia, valida o quadro e reconstrói o texto."""
    preambulo, marcador, repeticoes = parametros_quadro(formato)
    inicio_marcador = len(preambulo)
    fim_marcador = inicio_marcador + len(marcador)
    marcador_recebido = bits[inicio_marcador:fim_marcador]
    erros_marcador = sum(
        recebido != esperado
        for recebido, esperado in zip(marcador_recebido, marcador)
    )
    limite_erros = max(1, len(marcador) * 3 // 32)
    if len(marcador_recebido) != len(marcador) or erros_marcador > limite_erros:
        raise ValueError(
            "Marcador nao encontrado. A gravacao pode estar baixa, ruidosa "
            "ou com a portadora incorreta."
        )

    bits_protegidos = bits[fim_marcador:]
    tamanho_protegido = 16 * repeticoes
    if len(bits_protegidos) < tamanho_protegido:
        raise ValueError("A gravacao terminou antes do cabecalho.")

    cabecalho = decodificar_repeticao(
        bits_protegidos[:tamanho_protegido], repeticoes
    )
    quantidade_bytes = bits_para_inteiro(cabecalho[:16])
    if not 1 <= quantidade_bytes <= MAXIMO_BYTES:
        raise ValueError(
            "Cabecalho corrompido: o tamanho recebido nao e valido. "
            "Reduza o ruido ou aproxime os computadores."
        )

    quantidade_logica = 16 + quantidade_bytes * 8 + 8
    quantidade_fisica = quantidade_logica * repeticoes
    if len(bits_protegidos) < quantidade_fisica:
        raise ValueError(
            "A gravacao terminou antes do final da mensagem. "
            "Aumente o tempo de gravacao do receptor."
        )

    logicos = decodificar_repeticao(
        bits_protegidos[:quantidade_fisica], repeticoes
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
    """Modula bits FISICOS: bit 1 = 0 graus; bit 0 = 180 graus."""
    validar_taxa_fisica(taxa_bits, portadora)
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
    """taxa_bits e a taxa UTIL dos caracteres; o audio usa tres vezes isso."""
    validar_parametros(taxa_bits, portadora)
    bits = montar_quadro(texto)
    modulado = modular_bpsk(bits, calcular_taxa_fisica(taxa_bits), portadora)
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
    if quantidade <= 0 or inicio < 0:
        return None
    comecos = inicio + np.arange(quantidade) * amostras_por_bit
    finais = comecos + amostras_por_bit
    if finais[-1] >= len(acumulada_complexa):
        return None
    return acumulada_complexa[finais] - acumulada_complexa[comecos]


def preparar_recepcao(sinal, taxa_bits, portadora):
    """Filtra e mistura uma unica vez, mesmo ao tentar diferentes quadros."""
    sinal_filtrado = filtrar_em_torno_da_portadora(
        sinal, taxa_bits, portadora
    )

    n = np.arange(len(sinal_filtrado))
    oscilador_complexo = np.exp(-2j * np.pi * portadora * n /
                                TAXA_AMOSTRAGEM)
    misturado = sinal_filtrado * oscilador_complexo
    return np.concatenate([[0j], np.cumsum(misturado)])


def buscar_inicios(acumulada, amostras_por_bit, conhecidos):
    """Retem varios picos: um clique forte nao deve encerrar a busca."""
    quantidade_conhecida = len(conhecidos)
    ultimo = len(acumulada) - 1 - quantidade_conhecida * amostras_por_bit
    if ultimo < 0:
        return []
    passo = max(1, amostras_por_bit // 8)
    inicios = np.arange(0, ultimo + 1, passo)

    def avaliar(posicoes):
        indices = posicoes[:, None] + np.arange(quantidade_conhecida) * amostras_por_bit
        simbolos = acumulada[indices + amostras_por_bit] - acumulada[indices]
        produtos = simbolos * conhecidos
        blocos = produtos.reshape(len(posicoes), -1, 8).sum(axis=2)
        energia = np.mean(abs(simbolos), axis=1)
        metrica = np.sum(abs(blocos), axis=1) / (np.sum(abs(simbolos), axis=1) + 1e-15)
        return metrica, energia

    # Limita a memoria tambem em mensagens longas e com treinamento maior.
    metricas = np.empty(len(inicios))
    energias = np.empty(len(inicios))
    for primeiro in range(0, len(inicios), 1024):
        trecho = slice(primeiro, primeiro + 1024)
        metricas[trecho], energias[trecho] = avaliar(inicios[trecho])
    referencia = max(float(np.percentile(energias, 90)), 1e-12)
    # Satura o peso da energia: o transitorio do microfone pode ser dezenas
    # de vezes maior que a mensagem e antes dominava toda a sincronizacao.
    notas = metricas * np.sqrt(np.minimum(energias / referencia, 1.0))
    escolhidos = []
    for indice in np.argsort(notas)[::-1]:
        inicio = int(inicios[indice])
        if notas[indice] < 0.40:
            break
        if any(abs(inicio - outro) < amostras_por_bit for outro in escolhidos):
            continue
        vizinhos = np.arange(max(0, inicio - passo), min(ultimo, inicio + passo) + 1)
        m, e = avaliar(vizinhos)
        nota = m * np.sqrt(np.minimum(e / referencia, 1.0))
        escolhidos.append(int(vizinhos[np.argmax(nota)]))
        if len(escolhidos) == 12:
            break
    return escolhidos


def estimar_portadora(simbolos, conhecidos):
    """Estima fase e frequencia sem deixar um pico de amplitude dominar."""
    produtos = simbolos * conhecidos
    produtos /= np.maximum(abs(produtos), np.median(abs(produtos)) * 0.5 + 1e-15)
    indices = np.arange(len(produtos))

    def procurar(derivas):
        correlacoes = np.exp(-1j * derivas[:, None] * indices) @ produtos
        melhor = int(np.argmax(abs(correlacoes)))
        return float(derivas[melhor]), correlacoes[melhor]

    deriva, _ = procurar(np.linspace(-0.8, 0.8, 321))
    # A antiga grade de 0,0025 rad/bit acumulava erro em mensagens longas.
    deriva, correlacao = procurar(np.linspace(deriva - 0.005, deriva + 0.005, 201))
    metrica = float(abs(correlacao) / (sum(abs(produtos)) + 1e-15))
    return float(np.angle(correlacao)), deriva, metrica


def decidir_bits(simbolos, fase, deriva, treinamento, taxa_fisica=100):
    """Acompanha pequenas mudancas de fase durante os dados (BPSK)."""
    indices = np.arange(len(simbolos))
    corrigidos = simbolos * np.exp(-1j * (fase + deriva * indices))
    fase_residual = 0.0
    velocidade = 0.0
    piso = np.median(abs(simbolos[:treinamento])) * 0.1
    escala_tempo = 100 / taxa_fisica
    for i in range(treinamento, len(corrigidos)):
        valor = corrigidos[i] * np.exp(-1j * fase_residual)
        corrigidos[i] = valor
        erro = float(np.angle(valor * (1 if valor.real >= 0 else -1)))
        if abs(valor) > piso:
            velocidade += 0.0008 * escala_tempo ** 2 * erro
            fase_residual += 0.08 * escala_tempo * erro
        fase_residual += velocidade
    return (corrigidos.real >= 0).astype(int).tolist()


def equalizar_simbolos(acumulada, inicio, amostras_por_bit, conhecidos, tamanho_preambulo,
                      taps=13, deriva=0.0):
    """FIR complexo treinado: compensa ecos que misturam bits vizinhos.

    Duas amostras por bit toleram atrasos fracionarios do canal. Ignoramos a
    primeira metade do preambulo, afetada pelo transitorio do microfone.
    A validacao leave-one-out avalia cada bit SEM usa-lo no proprio ajuste.
    """
    if amostras_por_bit < 2:
        return None
    quantidade = (len(acumulada) - 1 - inicio) // amostras_por_bit
    if quantidade < len(conhecidos):
        return None
    # Alterna os comprimentos quando ha um numero impar de amostras por bit,
    # sem acumular um erro de meia amostra a cada simbolo.
    indices = inicio + np.arange(quantidade * 2 + 1) * amostras_por_bit // 2
    z = (acumulada[indices[1:]] - acumulada[indices[:-1]]) / np.diff(indices)
    z *= np.exp(-1j * deriva * np.arange(len(z)) / 2)
    posicoes = np.arange(quantidade) * 2
    X = np.array([
        z[np.clip(posicoes + i - taps // 2, 0, len(z) - 1)]
        for i in range(taps)
    ]).T
    descarte = tamanho_preambulo // 2
    X /= max(float(np.sqrt(np.mean(abs(X[descarte:len(conhecidos)]) ** 2))), 1e-12)
    treino = X[descarte:len(conhecidos)]
    alvo = conhecidos[descarte:]
    inversa = np.linalg.inv(treino.conj().T @ treino + 0.1 * np.eye(taps))
    coeficientes = inversa @ treino.conj().T @ alvo
    previstos = treino @ coeficientes
    influencia = np.real(np.sum((treino @ inversa) * treino.conj(), axis=1))
    validacao = (previstos - influencia * alvo) / np.maximum(1 - influencia, 1e-9)
    corretos = validacao.real * alvo > 0
    separacao = tamanho_preambulo - descarte
    if np.mean(corretos[:separacao]) < 0.8 or np.mean(corretos[separacao:]) < 0.75:
        return None
    metrica = float(np.mean(np.clip(validacao.real * alvo, -1, 1)))
    if metrica < 0.4:
        return None
    return X @ coeficientes, metrica


def demodular_bpsk(sinal, taxa_bits, portadora):
    """Recebe taxa UTIL e reconhece tambem as gravacoes das versoes antigas."""
    validar_parametros(taxa_bits, portadora)
    tentativas = [
        (calcular_taxa_fisica(taxa_bits), ["atual"]),
        # Nas versoes anteriores, o parametro do menu era a taxa fisica.
        (taxa_bits, ["anterior", "antigo"]),
    ]
    erros = []
    for taxa_fisica, formatos in tentativas:
        try:
            return demodular_na_taxa_fisica(sinal, taxa_fisica, portadora, formatos)
        except ValueError as erro:
            erros.append(str(erro))
    raise ValueError(erros[0])


def demodular_na_taxa_fisica(sinal, taxa_bits, portadora, formatos):
    """So aceita sincronizacao depois de validar marcador, tamanho e checksum."""
    validar_taxa_fisica(taxa_bits, portadora)
    sinal = np.asarray(sinal, dtype=np.float64)
    if sinal.ndim != 1 or not len(sinal) or not np.all(np.isfinite(sinal)):
        raise ValueError("A gravacao precisa conter amostras mono validas.")
    amostras_por_bit = TAXA_AMOSTRAGEM // taxa_bits
    if len(sinal) < 48 * amostras_por_bit:
        raise ValueError("Nao ha amostras suficientes para sincronizar.")
    acumulada = preparar_recepcao(sinal, taxa_bits, portadora)
    tentativas_equalizacao = []
    melhor_erro = None

    def validar(bits, formato, inicio, fase, deriva, metrica, modo):
        nonlocal melhor_erro
        preambulo, marcador, repeticoes = parametros_quadro(formato)
        if modo == "coerente" and np.mean(np.array(bits[:len(preambulo)]) == preambulo) < 0.8:
            return None
        try:
            texto, usados = interpretar_quadro(bits, formato)
        except ValueError as erro:
            if melhor_erro is None and "Marcador nao encontrado" not in str(erro):
                melhor_erro = str(erro)
            return None
        if modo == "equalizado" and repeticoes > 1:
            dados = np.array(bits[len(preambulo) + len(marcador):usados]).reshape(-1, repeticoes)
            maiorias = np.sum(dados, axis=1) > repeticoes // 2
            if np.mean(dados == maiorias[:, None]) < 0.9:
                return None
        diagnostico = {
            "inicio_amostra": int(inicio),
            "fase_graus": float(np.degrees(fase)) if modo == "coerente" else None,
            "deriva_hz": float(deriva * taxa_bits / (2 * np.pi)),
            "metrica_sincronizacao": float(metrica), "bits_decodificados": usados,
            "formato": formato, "modo": modo, "checksum_valido": True,
            "taxa_fisica_bps": taxa_bits,
            "taxa_util_bps": taxa_bits / repeticoes,
            "repeticoes": repeticoes,
        }
        return texto, bits, diagnostico

    for formato in formatos:
        preambulo, marcador, _ = parametros_quadro(formato)
        conhecidos = np.array(preambulo + marcador) * 2.0 - 1
        candidatos = buscar_inicios(acumulada, amostras_por_bit, conhecidos)
        for inicio in candidatos:
            quantidade = (len(sinal) - inicio) // amostras_por_bit
            simbolos = integra_simbolos(acumulada, inicio, quantidade, amostras_por_bit)
            fase, deriva, metrica = estimar_portadora(simbolos[:len(conhecidos)], conhecidos)
            if metrica >= 0.55:
                bits = decidir_bits(simbolos, fase, deriva, len(conhecidos), taxa_bits)
                resultado = validar(bits, formato, inicio, fase, deriva, metrica, "coerente")
                if resultado is not None:
                    return resultado
            tentativas_equalizacao.append((formato, inicio, conhecidos, deriva))

    # So recorre ao equalizador quando a recepcao coerente simples falhou.
    # Cada alinhamento precisa passar validacao independente e checksum;
    # nao basta ajustar o marcador conhecido e declarar sincronizacao.
    for formato, centro, conhecidos, deriva in tentativas_equalizacao:
        preambulo, _, _ = parametros_quadro(formato)
        passo = max(1, amostras_por_bit // 16)
        for deslocamento in range(-amostras_por_bit // 2, amostras_por_bit // 2 + 1, passo):
            inicio = centro + deslocamento
            if inicio < 0:
                continue
            # Mantem aproximadamente o mesmo alcance em segundos dos filtros
            # que recuperaram a gravacao da sala (13 taps em 100 bits/s).
            tamanhos = [min(61, 2 * round(6 * taxa_bits / 100) + 1),
                        max(5, 2 * round(2 * taxa_bits / 100) + 1)]
            for taps in (tamanhos if formato != "antigo" else [5]):
                for compensacao in [0.0, deriva]:
                    ajuste = equalizar_simbolos(acumulada, inicio, amostras_por_bit,
                                                conhecidos, len(preambulo), taps, compensacao)
                    if ajuste is None:
                        continue
                    simbolos, metrica = ajuste
                    bits = decidir_bits(simbolos, 0.0, 0.0, len(conhecidos), taxa_bits)
                    resultado = validar(bits, formato, inicio, 0.0, compensacao, metrica, "equalizado")
                    if resultado is not None:
                        return resultado
    if melhor_erro:
        raise ValueError(melhor_erro)
    raise ValueError(
        "Sincronizacao fraca ou marcador nao encontrado: nenhum quadro passou "
        "na validacao. Confira a taxa, a portadora e o microfone; "
        "desative supressao de ruido e melhorias de voz na entrada de audio."
    )


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
    """Lobulo principal dos pulsos fisicos retangulares (taxa recebida UTIL)."""
    taxa_fisica = calcular_taxa_fisica(taxa_bits)
    return portadora - taxa_fisica, portadora + taxa_fisica


def plotar_fft(sinal, titulo, caminho, taxa_bits, portadora, mostrar=True, taxa_fisica=None):
    plt = obter_matplotlib()
    frequencias, db = calcular_fft_db(sinal)
    if taxa_fisica is None:
        taxa_fisica = calcular_taxa_fisica(taxa_bits)
    inferior, superior = portadora - taxa_fisica, portadora + taxa_fisica

    figura, eixo = plt.subplots(figsize=(11, 5), constrained_layout=True)
    eixo.plot(frequencias, db, linewidth=0.8)
    eixo.axvline(portadora, color="black", linestyle=":",
                 label=f"portadora = {portadora} Hz")
    eixo.axvspan(inferior, superior, color="green", alpha=0.15,
                 label=f"lobulo principal ≈ {2 * taxa_fisica} Hz")
    largura_exibida = max(1_000, 1.5 * taxa_fisica)
    eixo.set_xlim(max(0, portadora - largura_exibida), portadora + largura_exibida)
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
        mascara = (f >= portadora - 1_200) & (f <= portadora + 1_200)
        fisica = calcular_taxa_fisica(taxa)
        eixo.plot(f[mascara], db[mascara], linewidth=0.9,
                  label=f"{taxa} uteis/s | {fisica} fisicos/s | banda ≈ {2*fisica} Hz")

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
    taxa_fisica = calcular_taxa_fisica(taxa_bits)
    duracao_bits = len(bits) / taxa_fisica
    inferior, superior = banda_teorica(taxa_bits, portadora)
    dados = texto.encode("utf-8")

    print("\n--- DIAGNOSTICO DO EMISSOR ---")
    print(f"Texto: {texto}")
    print(f"Bytes UTF-8: {list(dados)}")
    print(f"Primeiros bits: {''.join(map(str, bits[:96]))}")
    print(f"Total do quadro: {len(bits)} bits")
    print(f"Taxa util dos caracteres: {taxa_bits} bits/s")
    print(f"Taxa fisica BPSK: {taxa_fisica} bits/s (repeticao {REPETICOES}x)")
    print(f"Duracao apenas dos caracteres: {len(dados) * 8 / taxa_bits:.3f} s")
    print(f"Duracao dos bits: {duracao_bits:.3f} s")
    print(f"Duracao total com silencios: {len(sinal)/TAXA_AMOSTRAGEM:.3f} s")
    print(f"Amostras por bit fisico: {TAXA_AMOSTRAGEM // taxa_fisica}")
    print(f"Portadora: {portadora} Hz")
    print(
        f"Lobulo principal: {inferior} a {superior} Hz "
        f"(largura aproximada de {2 * taxa_fisica} Hz)"
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
    # Guarda cada tentativa: antes o proximo teste apagava a gravacao anterior.
    pasta = PASTA_RESULTADOS / "capturas" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    pasta.mkdir(parents=True, exist_ok=False)
    salvar_wav(pasta / "audio_recebido.wav", sinal)
    relatorio = {
        "taxa_util_configurada_bps": taxa_bits,
        "taxa_fisica_configurada_bps": calcular_taxa_fisica(taxa_bits),
        "portadora_hz": portadora,
        "taxa_amostragem": TAXA_AMOSTRAGEM, "duracao_s": len(sinal) / TAXA_AMOSTRAGEM,
    }
    try:
        # A FFT precisa ser atualizada mesmo quando a decodificacao falhar.
        # Antes ela ficava com o grafico de uma tentativa antiga.
        plotar_fft(sinal, "FFT do sinal BPSK recebido", pasta / "fft_recebido.png",
                   taxa_bits, portadora, mostrar=False)
        (PASTA_GRAFICOS / "02_fft_recebido.png").write_bytes(
            (pasta / "fft_recebido.png").read_bytes()
        )
        texto, bits, diagnostico = demodular_bpsk(sinal, taxa_bits, portadora)
        if diagnostico["taxa_fisica_bps"] != calcular_taxa_fisica(taxa_bits):
            plotar_fft(sinal, "FFT do sinal BPSK recebido", pasta / "fft_recebido.png",
                       taxa_bits, portadora, mostrar=False,
                       taxa_fisica=diagnostico["taxa_fisica_bps"])
            (PASTA_GRAFICOS / "02_fft_recebido.png").write_bytes(
                (pasta / "fft_recebido.png").read_bytes()
            )
        relatorio.update(sucesso=True, diagnostico=diagnostico)
    except (ValueError, RuntimeError) as erro:
        relatorio.update(sucesso=False, erro=str(erro))
        raise
    finally:
        (pasta / "diagnostico.json").write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Gravacao e diagnostico preservados em {pasta}")
    imprimir_recepcao(texto, bits, diagnostico)


def imprimir_recepcao(texto, bits, diagnostico):

    print("\n--- DIAGNOSTICO DO RECEPTOR ---")
    print(f"Formato reconhecido: {diagnostico['formato']}")
    print(f"Recepcao: {diagnostico['modo']}; checksum correto")
    print(f"Taxa util detectada: {diagnostico['taxa_util_bps']:g} bits/s")
    print(f"Taxa fisica detectada: {diagnostico['taxa_fisica_bps']:g} bits/s")
    print(f"Inicio detectado na amostra: {diagnostico['inicio_amostra']}")
    if diagnostico["fase_graus"] is None:
        print("Fase compensada pelos coeficientes do equalizador")
    else:
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


def decodificar_arquivo(caminho, taxa_bits, portadora):
    """Reprocessa gravacoes sem microfone e sem sobrescrever os resultados."""
    sinal = carregar_wav(caminho)
    resultado = demodular_bpsk(sinal, taxa_bits, portadora)
    imprimir_recepcao(*resultado)
    return resultado


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
    print(f"Sincronizacao: {diagnostico['metrica_sincronizacao']:.3f}; modo: {diagnostico['modo']}")
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
        print(f"Configuracao: {taxa_bits} bits uteis/s | "
              f"{calcular_taxa_fisica(taxa_bits)} fisicos/s | portadora {portadora} Hz")
        print("=" * 66)
        print("1 - EMISSOR: digitar e transmitir uma mensagem")
        print("2 - RECEPTOR: gravar e decodificar uma mensagem")
        print("3 - Teste local do ultimo audio (sem microfone)")
        print("4 - Comparar taxas de 50, 100 e 200 bits UTEIS/s")
        print("5 - Comparar portadoras de 2,5, 4 e 5,5 kHz")
        print("6 - Alterar taxa de bits e portadora")
        print("7 - Mostrar FFT emitida e recebida")
        print("8 - Decodificar o ultimo audio recebido (sem gravar novamente)")
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
                    "Nova taxa UTIL em bits/s", taxa_bits
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
            elif escolha == "8":
                decodificar_arquivo(ARQUIVO_RECEBIDO, taxa_bits, portadora)
            elif escolha == "0":
                print("Programa encerrado.")
                break
            else:
                print("Opcao invalida.")
        except (FileNotFoundError, RuntimeError, ValueError, wave.Error) as erro:
            print(f"\nERRO: {erro}")


def executar():
    parser = argparse.ArgumentParser(description="Chat BPSK por audio")
    parser.add_argument("--decodificar", type=Path, help="WAV recebido para reprocessar sem microfone")
    parser.add_argument("--taxa", type=int, default=TAXA_BITS_PADRAO,
                        help="Bits UTEIS/s; novos quadros usam 3x fisicos/s (padrao: 100)")
    parser.add_argument("--portadora", type=int, default=PORTADORA_PADRAO, help="Portadora em Hz (padrao: 4000)")
    args = parser.parse_args()
    if args.decodificar:
        try:
            decodificar_arquivo(args.decodificar, args.taxa, args.portadora)
        except (OSError, RuntimeError, ValueError, wave.Error) as erro:
            parser.exit(1, f"ERRO: {erro}\n")
    else:
        menu()


if __name__ == "__main__":
    executar()
