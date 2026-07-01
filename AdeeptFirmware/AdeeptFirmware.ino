#include <Servo.h>

// Instanciação
Servo servoBase;
Servo servoOmbro;
Servo servoCotovelo;
Servo servoPulso;
Servo servoGarra;

void setup() {
  Serial.begin(115200);
  
  // Mapeamento exato de hardware
  servoBase.attach(9);     // D9
  servoOmbro.attach(6);    // D6
  servoCotovelo.attach(5); // D5
  servoPulso.attach(3);    // D3
  servoGarra.attach(11);   // D11
  
  // Posição inicial de calibração (Home)
  servoBase.write(90);
  servoOmbro.write(90);
  servoCotovelo.write(90);
  servoPulso.write(90);
  servoGarra.write(90);
}

void loop() {
  // Leitura do buffer e extração do payload
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\n');
    
    int b, o, c, p, g;
    if (sscanf(data.c_str(), "<%d,%d,%d,%d,%d>", &b, &o, &c, &p, &g) == 5) {
      servoBase.write(b);
      servoOmbro.write(o);
      servoCotovelo.write(c);
      servoPulso.write(p);
      servoGarra.write(g);
    }
  }
}