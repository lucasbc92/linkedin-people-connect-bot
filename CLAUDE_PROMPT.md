# Original Prompt for LinkedIn People Connection Bot

This document contains the original prompt that was used to generate the LinkedIn People Connection Bot.

## The Request

Ok. For max size message issues, I'll show you the portion of the HTML that has the list of tech recruiters. It's pasted now. (shown in search-results-container-example.html file)

Now, this is an example of the **Connect button**:

```html
<button aria-label="Invite Luana Marques to connect" id="ember8806" class="artdeco-button artdeco-button--2 artdeco-button--secondary ember-view" type="button">
    <span class="artdeco-button__text">
        Connect
    </span>
</button>
```

## Workflow Description

### Step 1: Click Connect Button
After clicking Connect, a window appears for you to choose if you want to add the person with or without a note. As I'm using LinkedIn premium, I can send many notes as I like, so I'll want to send a note to every recruiter.

### Step 2: Click "Add a Note"
So, after the window opens, click **"Add a note"** button, that is this one:

```html
<button aria-label="Add a note" id="ember8896" class="artdeco-button artdeco-button--muted artdeco-button--2 artdeco-button--secondary ember-view mr1">
    <span class="artdeco-button__text">
        Add a note
    </span>
</button>
```

### Step 3: Fill Message and Send
Then, after clicking "Add a note", there's a text box where you write the message, then click Send to successfully send a connection invite with a note.

#### Original Message Template
I want you to paste the quoted message below into the text box:

```
"Olá, ! 👋 
Sou Full Stack Developer focado em backend com 5+ anos de experiência, sendo os últimos 3 anos em Java Spring 🍃 & React ⚛️. Apaixonado por café ☕, simplificar problemas complexos 💡 e entregar soluções robustas 💪. 
Espero que meu perfil desperte seu interesse! 🚀"
```

#### Text Box HTML
```html
<textarea name="message" rows="2" placeholder="Ex: We know each other from..." id="custom-message" class="ember-text-area ember-view connect-button-send-invite__custom-message connect-button-send-invite__custom-message--no-styling connect-button-send-invite__custom-message--block" minlength="1" style="height: 27px;"></textarea>
```

#### Send Button HTML
```html
<button disabled="" aria-label="Send invitation" id="ember9359" class="artdeco-button artdeco-button--2 artdeco-button--primary artdeco-button--disabled ember-view ml1">
    <span class="artdeco-button__text">
        Send
    </span>
</button>
```

## Button States and Behavior

### After Sending
After that, the Connect button from the tech recruiter I invited changes to **"Pending"**. That's when you can go to the next Connect button and do all the same thing.

### Other Button Types

#### Follow Buttons
Note that there may be some **"Follow"** buttons in the middle of the "Connect" ones. These Follow buttons can be clicked once then move on to the next button, because I can't send a note when just following.

#### Message Buttons
And there are some with **"Message"** buttons that means that I'm already connected to these tech recruiters, so you can just ignore them. There's no use to send that compliment message if I already connected with the tech recruiter.

## Navigation

### Moving to Next Page
You'll stop when you reach the last Connect button. There, you can hit the **"Next"** button to go to the next page. There, you'll wait the page to load and get the `search-results-container` again, and do the same operations until there's no next page (page 100 is usually the last).

#### Next Button HTML
```html
<button aria-label="Next" id="ember9585" class="artdeco-button artdeco-button--muted artdeco-button--icon-right artdeco-button--1 artdeco-button--tertiary ember-view artdeco-pagination__button artdeco-pagination__button--next" type="button">
    <svg role="none" aria-hidden="true" class="artdeco-button__icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" data-supported-dps="16x16" data-test-icon="chevron-right-small" data-rtl="true">
        <use href="#chevron-right-small" width="16" height="16"></use>
    </svg>
    <span class="artdeco-button__text">
        Next
    </span>
</button>
```

## Final Request

So, can you do this herculean labor to me? Use Selenium.

---

**Note**: The original HTML sample data that was provided with this prompt is stored in a separate file (`linkedin_sample_html.html`) due to its size.