import cv2                       # Captura de video e manipulacao de imagens
import os                        # Manipulacao de pastas e caminhos
import serial                    # Comunicacao serial com o Arduino
import serial.tools.list_ports   # Listagem de portas COM disponiveis
import time                      # Controle de cooldown
import datetime                  # Timestamps para fotos de acesso negado
import numpy as np               # Operacoes numericas no pre-processamento
import tf_keras as keras         # Keras 2 legado — necessario para modelos Teachable Machine

# ── Configuracoes ─────────────────────────────────────────────────────────────

PASTA_NEGADOS    = "acessos_negados"
BAUD_RATE        = 9600
COOLDOWN         = 5.0    # Segundos entre comandos enviados para o mesmo resultado
CONFIANCA_MINIMA = 0.95   # Confianca minima para considerar reconhecido
CONFIRMACOES_MIN = 3      # Confirmacoes consecutivas antes de enviar ABRIR
PORTA_MANUAL     = None   # Ex: "COM3" para fixar a porta; None = deteccao automatica

# ── Carrega labels e modelo ────────────────────────────────────────────────────

for arquivo in ["labels.txt", "keras_model.h5"]:
    if not os.path.exists(arquivo):
        print(f"[ERRO] Arquivo nao encontrado: {arquivo}")
        exit()

with open("labels.txt", "r") as f:
    classes = [linha.strip().split(" ", 1)[1] for linha in f if linha.strip()]

print(f"[INFO] Classes carregadas: {classes}")

# Teachable Machine exporta DepthwiseConv2D com 'groups', argumento removido
# no Keras 3. A subclasse descarta o argumento para carregar sem erro.
class DepthwiseConv2DCompat(keras.layers.DepthwiseConv2D):
    def __init__(self, *args, **kwargs):
        kwargs.pop("groups", None)
        super().__init__(*args, **kwargs)

try:
    with keras.utils.custom_object_scope({"DepthwiseConv2D": DepthwiseConv2DCompat}):
        modelo = keras.models.load_model("keras_model.h5", compile=False)
    print(f"[OK] Modelo carregado.\n")
except Exception as e:
    print(f"[ERRO] Falha ao carregar modelo: {e}")
    exit()

os.makedirs(PASTA_NEGADOS, exist_ok=True)

# ── Detecta porta COM do Arduino ──────────────────────────────────────────────

def encontrar_porta_arduino():
    for porta in serial.tools.list_ports.comports():
        if any(kw in porta.description for kw in ["Arduino", "CH340", "USB"]):
            return porta.device
    portas = list(serial.tools.list_ports.comports())
    return portas[0].device if portas else None

porta_com = PORTA_MANUAL if PORTA_MANUAL else encontrar_porta_arduino()

if porta_com is None:
    print("[ERRO] Nenhuma porta COM encontrada. Verifique se o Arduino esta conectado.")
    exit()

print(f"[INFO] Conectando ao Arduino na porta {porta_com}...")

try:
    arduino = serial.Serial(porta_com, BAUD_RATE, timeout=1)
    time.sleep(2)  # Aguarda o Arduino reiniciar apos abrir a porta serial
    print(f"[OK] Arduino conectado em {porta_com}.\n")
except serial.SerialException as e:
    print(f"[ERRO] Nao foi possivel conectar ao Arduino: {e}")
    exit()

# ── Abre a webcam ─────────────────────────────────────────────────────────────

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("[ERRO] Nao foi possivel abrir a camera.")
    arduino.close()
    exit()

print("[INFO] Reconhecimento iniciado. Pressione ESC para encerrar.\n")

# ── Variaveis de controle do loop ─────────────────────────────────────────────

confirmacoes  = {}   # { nome: contagem_de_confirmacoes_consecutivas }
ultimo_envio  = {}   # { chave: timestamp_do_ultimo_comando_enviado }
label_exibida = ""
cor_label     = (200, 200, 200)

# ── Loop principal ─────────────────────────────────────────────────────────────

while True:
    ret, frame = camera.read()

    if not ret:
        print("[ERRO] Falha ao capturar frame.")
        break

    # ── Pre-processa o frame para o modelo ────────────────────────────────────
    # Teachable Machine treina com RGB (navegador); OpenCV captura em BGR
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (224, 224))
    img = np.array(img, dtype=np.float32)
    img = (img / 127.5) - 1.0
    img = np.expand_dims(img, axis=0)

    # ── Inferencia ────────────────────────────────────────────────────────────
    try:
        predicao  = modelo.predict(img, verbose=0)[0]
        indice    = int(np.argmax(predicao))
        confianca = float(predicao[indice])
        nome      = classes[indice]
    except Exception as e:
        print(f"[AVISO] Erro na inferencia: {e}")
        cv2.imshow("Reconhecimento Facial — Fechadura Inteligente", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
        continue

    reconhecido = (nome != "desconhecido") and (confianca >= CONFIANCA_MINIMA)

    if reconhecido:
        # Incrementa confirmacoes para este nome e zera os demais
        confirmacoes = {nome: confirmacoes.get(nome, 0) + 1}
        contagem = confirmacoes[nome]

        if contagem < CONFIRMACOES_MIN:
            label_exibida = f"Verificando {nome}... ({contagem}/{CONFIRMACOES_MIN})"
            cor_label = (0, 165, 255)  # Laranja
        else:
            label_exibida = f"{nome} ({confianca:.0%})"
            cor_label = (0, 255, 0)  # Verde

            agora  = time.time()
            if agora - ultimo_envio.get(nome, 0) >= COOLDOWN:
                ultimo_envio[nome] = agora
                arduino.write(b"ABRIR\n")
                print(f"[ACESSO LIBERADO] {nome} (confianca: {confianca:.2%})")

    else:
        confirmacoes  = {}
        label_exibida = f"Desconhecido ({confianca:.0%})"
        cor_label = (0, 0, 255)  # Vermelho

        agora = time.time()
        if agora - ultimo_envio.get("desconhecido", 0) >= COOLDOWN:
            ultimo_envio["desconhecido"] = agora
            arduino.write(b"NEGAR\n")
            print(f"[ACESSO NEGADO] {nome} (confianca: {confianca:.2%})")

            timestamp    = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            caminho_foto = os.path.join(PASTA_NEGADOS, f"negado_{timestamp}.jpg")
            cv2.imwrite(caminho_foto, frame)
            print(f"[FOTO] Salva em: {caminho_foto}")

    # ── Exibe label no canto superior esquerdo ────────────────────────────────
    if label_exibida:
        cv2.rectangle(frame, (0, 0), (380, 40), cor_label, cv2.FILLED)
        cv2.putText(
            frame, label_exibida,
            (10, 28),
            cv2.FONT_HERSHEY_DUPLEX,
            0.8, (255, 255, 255), 1
        )

    cv2.imshow("Reconhecimento Facial — Fechadura Inteligente", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        print("[INFO] Encerrando reconhecimento.")
        break

# ── Limpeza final ─────────────────────────────────────────────────────────────

camera.release()
cv2.destroyAllWindows()
arduino.close()
print("[INFO] Programa encerrado.")
