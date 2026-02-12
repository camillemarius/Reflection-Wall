from app.ui.display import Display
from app.chatbot.chatbot_groq import write_to_ai
import time

def main():
    display = Display(simulation=True)  # später False für echtes I2C

    display.set_text("System startet...")
    time.sleep(2)

    question = "Was ist der Sinn des Lebens?"
    answer = write_to_ai(question)


    print("\n")
    print("AI:", answer)
    print("\n")

    display.set_text(answer)

if __name__ == "__main__":
    main()
