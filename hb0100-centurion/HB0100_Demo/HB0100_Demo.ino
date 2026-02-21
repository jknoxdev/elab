//Demo for HackerBox 0100
//  see details at HackerBoxes.com
//
//Exercises Basic Features of
//  Centurion Bus Analysis Target PCB
//
//Required Libraries:
//  GFX Library for Arduino (by Moon On Our Nation)
//    available by searching Manage Libraries
//  MPU9250_WE by Wolfgang Ewald
//    available by searching Manage Libraries

#include <Arduino_GFX_Library.h>
#include <MPU9250_WE.h>
#include <Wire.h>

#define MPU9250_ADDR 0x68
#define MPU_SDA  0
#define MPU_SCL  1

MPU9250_WE myMPU9250 = MPU9250_WE(MPU9250_ADDR);

#define TFTDIN   11
#define TFTCLK   10
#define TFTDC    8
#define TFTCS    9
#define TFTRST   12

// connect GC9A01 circular display
Arduino_DataBus *bus = new Arduino_SWSPI(TFTDC, TFTCS, TFTCLK, TFTDIN, -1);
Arduino_GFX *gfx = new Arduino_GC9A01(bus, TFTRST, 0, true);

// pins for six switches
#define SW_UP   16
#define SW_DN   18
#define SW_LF   19
#define SW_RT   17
#define SW_A    21
#define SW_B    20

#define BLACK   0x0000
#define RED     0xF800
#define YELLOW  0xFFE0
#define WHITE   0xFFFF

void setup(void)
{
  Serial.begin(9600);
  Wire.setSDA(MPU_SDA);
  Wire.setSCL(MPU_SCL);
  Wire.begin();
  if(!myMPU9250.init()){
    Serial.println("MPU9250 does not respond");
  }
  else{
    Serial.println("MPU9250 is connected");
  }

  Serial.println("Position you MPU9250 flat and don't move it - calibrating...");
  delay(1000);
  myMPU9250.autoOffsets();
  Serial.println("Done!");
  myMPU9250.setAccRange(MPU9250_ACC_RANGE_2G);
  myMPU9250.enableAccDLPF(true);
  myMPU9250.setAccDLPF(MPU9250_DLPF_6); 

  //button pins needs pulldowns since they close directly to 3V3 (active high)
  pinMode(SW_LF, INPUT_PULLDOWN);
  pinMode(SW_RT, INPUT_PULLDOWN);

  gfx->begin();
gfx->fillScreen(BLACK);
  //draw a bunch of concentric circles - just for fun
  for(int r=1; r<120; r++)
    gfx->drawCircle(120, 120, r, random(0xffff));
  
  delay(2000);

  gfx->fillScreen(BLACK);
}

void loop()
{
  char strBuf[20];
  xyzFloat angle;
  
  angle = myMPU9250.getAngles();
  SerPrintMPU();
  ReadButtons();

  gfx->setTextSize(2);
  gfx->setTextColor(YELLOW, BLACK);

  gfx->setCursor(70, 60);
  sprintf(strBuf, "X: %4.0f", angle.x);
  gfx->println(strBuf);    

  gfx->setCursor(70, 80);
  sprintf(strBuf, "Y: %4.0f", angle.y);
  gfx->println(strBuf);
   
  gfx->setCursor(70, 100);
  sprintf(strBuf, "Z: %4.0f", angle.z);
  gfx->println(strBuf);
  
  delay(30);
}

void ReadButtons(void){
  char strBuf[20];
  int bRT, bLF, bUP, bDN, bA, bB;

  bRT = (digitalRead(SW_RT)) ? 1 : 0;
  bLF = (digitalRead(SW_LF)) ? 1 : 0;
  bUP = (digitalRead(SW_UP)) ? 1 : 0;
  bDN = (digitalRead(SW_DN)) ? 1 : 0;
  bA  = (digitalRead(SW_A) ) ? 1 : 0;
  bB  = (digitalRead(SW_B) ) ? 1 : 0;
 
  gfx->setTextSize(2);
  gfx->setTextColor(RED, BLACK);
 
  gfx->setCursor(50, 140);
  sprintf(strBuf, "Buttons------");
  gfx->println(strBuf);
  
  gfx->setCursor(50, 160);
  sprintf(strBuf, "A, B: %d,%d", bA, bB);
  gfx->println(strBuf);
  Serial.print("Buttons A,B: ");
  Serial.print(strBuf);

  gfx->setCursor(50, 180);
  sprintf(strBuf, "UDLR: %d,%d,%d,%d", bUP, bDN, bLF, bRT);
  gfx->println(strBuf);
  Serial.print("  |  Buttons UP,DN,LF,RT: ");
  Serial.println(strBuf);

  Serial.println();
}

void SerPrintMPU(){
  xyzFloat angle = myMPU9250.getAngles();
  
  // Just home the cursor, don't clear
  Serial.print("\033[H");
  Serial.print("╔══════════════════════════╗\r\n");
  Serial.print("║     HB0100 Centurion     ║\r\n");
  Serial.print("╠══════════════════════════╣\r\n");
  Serial.printf("║  Angle x  = %8.2f deg ║\r\n", angle.x);
  Serial.printf("║  Angle y  = %8.2f deg ║\r\n", angle.y);
  Serial.printf("║  Angle z  = %8.2f deg ║\r\n", angle.z);
  Serial.print("╠══════════════════════════╣\r\n");
  Serial.printf("║  Orientation: %-11s║\r\n", myMPU9250.getOrientationAsString().c_str());
  Serial.print("╚══════════════════════════╝\r\n");
}
