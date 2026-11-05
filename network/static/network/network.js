/*
Network front-end: like/unlike, inline post editing and follow/unfollow.
All server calls are asynchronous fetch() requests; the page never reloads.
User-provided text is only ever written with textContent (never innerHTML).
*/
(() => {
    "use strict";

    const csrfToken =
        document.querySelector('meta[name="csrf-token"]')?.content ?? "";

    async function api(url, method, body) {
        const response = await fetch(url, {
            method,
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: body === undefined ? undefined : JSON.stringify(body),
        });
        let data = {};
        try {
            data = await response.json();
        } catch (_) {
            /* non-JSON error page */
        }
        if (!response.ok) {
            throw new Error(data.error || `Request failed (${response.status}).`);
        }
        return data;
    }

    function setError(container, message) {
        const el = container.querySelector(".post-error, .follow-error");
        if (el) el.textContent = message;
    }

    // ---- Like / Unlike ---------------------------------------------------
    async function toggleLike(button) {
        const article = button.closest(".post");
        button.disabled = true;
        setError(article, "");
        try {
            const data = await api(article.dataset.likeUrl, "POST");
            button.dataset.liked = String(data.liked);
            button.textContent = data.liked ? "Unlike" : "Like";
            button.classList.toggle("btn-secondary", data.liked);
            button.classList.toggle("btn-outline-secondary", !data.liked);
            article.querySelector(".like-count").textContent = data.likes;
        } catch (error) {
            setError(article, error.message);
        } finally {
            button.disabled = false;
        }
    }

    // ---- Inline editing ---------------------------------------------------
    function startEdit(editButton) {
        const article = editButton.closest(".post");
        if (article.classList.contains("editing")) return;

        const contentEl = article.querySelector(".post-content");
        const original = contentEl.textContent;

        const editor = document.createElement("div");
        editor.className = "post-editor";

        const textarea = document.createElement("textarea");
        textarea.className = "form-control";
        textarea.rows = 3;
        textarea.maxLength = Number(article.dataset.maxLength) || 500;
        textarea.value = original;
        textarea.setAttribute("aria-label", "Edit post content");

        const save = document.createElement("button");
        save.type = "button";
        save.className = "btn btn-primary btn-sm";
        save.textContent = "Save";

        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "btn btn-light btn-sm";
        cancel.textContent = "Cancel";

        editor.append(textarea, save, cancel);

        const close = () => {
            editor.remove();
            contentEl.hidden = false;
            editButton.hidden = false;
            article.classList.remove("editing");
        };

        cancel.addEventListener("click", () => {
            setError(article, "");
            close();
        });

        save.addEventListener("click", async () => {
            save.disabled = true;
            setError(article, "");
            try {
                const post = await api(article.dataset.editUrl, "PUT", {
                    content: textarea.value,
                });
                contentEl.textContent = post.content;
                close();
            } catch (error) {
                setError(article, error.message);
                save.disabled = false;
            }
        });

        article.classList.add("editing");
        contentEl.hidden = true;
        editButton.hidden = true;
        contentEl.after(editor);
        textarea.focus();
    }

    // ---- Follow / Unfollow ------------------------------------------------
    async function toggleFollow(button) {
        const card = button.closest(".profile-card");
        button.disabled = true;
        setError(card, "");
        try {
            const data = await api(card.dataset.followUrl, "POST");
            button.dataset.following = String(data.following);
            button.textContent = data.following ? "Unfollow" : "Follow";
            button.classList.toggle("btn-primary", !data.following);
            button.classList.toggle("btn-outline-primary", data.following);
            document.getElementById("followers-count").textContent = data.followers;
        } catch (error) {
            setError(card, error.message);
        } finally {
            button.disabled = false;
        }
    }

    document.addEventListener("click", (event) => {
        const target = event.target.closest("button");
        if (!target) return;
        if (target.classList.contains("like-btn")) toggleLike(target);
        else if (target.classList.contains("edit-btn")) startEdit(target);
        else if (target.classList.contains("follow-btn")) toggleFollow(target);
    });
})();
