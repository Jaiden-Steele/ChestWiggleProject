const int drivePin = 12;   
const int sensePin = 13;

int prevState = HIGH;   // store previous input state

const int SOLENOID2 = 2;
const int SOLENOID4 = 4;
const int SOLENOID7 = 7;
const int SOLENOID8 = 8;

float f = 15; //frequency of "chest" in Hz

void setup() {
  pinMode(drivePin, OUTPUT);
  pinMode(sensePin, INPUT_PULLUP);
  digitalWrite(drivePin, LOW);
  Serial.begin(9600);

  pinMode(SOLENOID2, OUTPUT);
  pinMode(SOLENOID4, OUTPUT);
  pinMode(SOLENOID7, OUTPUT);
  pinMode(SOLENOID8, OUTPUT);
  digitalWrite(drivePin, LOW);
}

void loop() {
  int currentState = digitalRead(sensePin);

  // only print when state changes
  if (currentState != prevState) {
    if (currentState == LOW) {
      Serial.println("On.");

    } else {
      Serial.println("Off.");
    }
    prevState = currentState;   // update stored state
  }

  if (currentState == LOW) {

      float stepMs = (1000.0 / f) ;  
      
      //solenoid at pin 2
      digitalWrite(SOLENOID2, HIGH);
      delay(10);
      digitalWrite(SOLENOID2, LOW);
      delay(stepMs - 10);

      //solenoid at pin 4
      digitalWrite(SOLENOID7, HIGH);
      delay(10);
      digitalWrite(SOLENOID7, LOW);
      delay(stepMs - 10);

      //solenoid at pin 
      digitalWrite(SOLENOID4, HIGH);
      delay(10);
      digitalWrite(SOLENOID4, LOW);
      delay(stepMs - 10);

      //solenoid at pin 
      digitalWrite(SOLENOID8, HIGH);
      delay(10);
      digitalWrite(SOLENOID8, LOW);
      delay(stepMs - 10);

    }
}
