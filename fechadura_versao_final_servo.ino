// ============================================================
//  Fechadura Inteligente — Arduino Uno
//  LEDs + Servo Motor
// ============================================================

#include <Servo.h>  // Biblioteca do servo motor

// --- PINOS ---
const int LED_VERDE    = 6;   // LED verde → acesso permitido
const int LED_VERMELHO = 7;   // LED vermelho → acesso negado
const int PINO_SERVO   = 9;   // Servo motor → simula a fechadura

// --- ÂNGULOS DO SERVO ---
const int ANGULO_ABERTO  = 90;  // Posição aberta (fechadura liberada)
const int ANGULO_FECHADO = 0;   // Posição fechada (fechadura travada)

// --- OBJETO SERVO ---
Servo servo;

// ============================================================
void setup() {
  Serial.begin(9600);

  // Configura os pinos dos LEDs como saída
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_VERMELHO, OUTPUT);

  // Inicializa o servo e garante que começa na posição fechada
  servo.attach(PINO_SERVO);
  servo.write(ANGULO_FECHADO);

  // Teste inicial: pisca os dois LEDs uma vez ao ligar
  digitalWrite(LED_VERDE, HIGH);
  digitalWrite(LED_VERMELHO, HIGH);
  delay(500);
  digitalWrite(LED_VERDE, LOW);
  digitalWrite(LED_VERMELHO, LOW);

  Serial.println("Sistema pronto. Aguardando comando...");
}

// ============================================================
void loop() {
  if (Serial.available() > 0) {
    String comando = Serial.readStringUntil('\n');
    comando.trim(); // Remove espaços e \r

    if (comando == "ABRIR") {
      acessoPermitido();
    } else if (comando == "NEGAR") {
      acessoNegado();
    }
  }
}

// ============================================================
//  ACESSO PERMITIDO
//  LED Verde acende + Servo abre por 3 segundos
// ============================================================
void acessoPermitido() {
  Serial.println(">> Acesso PERMITIDO");

  // Acende o LED verde
  digitalWrite(LED_VERDE, HIGH);

  // Abre a fechadura girando o servo para a posição aberta
  servo.write(ANGULO_ABERTO);

  // Mantém aberto por 3 segundos
  delay(3000);

  // Fecha a fechadura e apaga o LED
  servo.write(ANGULO_FECHADO);
  digitalWrite(LED_VERDE, LOW);
}

// ============================================================
//  ACESSO NEGADO
//  LED Vermelho pisca 3 vezes + Servo permanece fechado
// ============================================================
void acessoNegado() {
  Serial.println(">> Acesso NEGADO");

  // Garante que o servo permanece fechado
  servo.write(ANGULO_FECHADO);

  // Pisca o LED vermelho 3 vezes
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_VERMELHO, HIGH);
    delay(300);
    digitalWrite(LED_VERMELHO, LOW);
    delay(300);
  }
}
