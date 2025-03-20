"use strict";
function addTodo() {
    const input = document.getElementById("todo-input");
    const todoList = document.getElementById("todo-list");
    
    if (input.value.trim() !== "") {
        const li = document.createElement("li");
        li.classList.add("list");
        li.innerHTML = `${input.value} `;
        const completeButton = document.createElement("button");
        completeButton.classList.add("greenbutton");
        completeButton.innerText = "완료";
        completeButton.addEventListener("click", () => completeTodo(li));
        li.appendChild(completeButton);
        todoList.appendChild(li);
        input.value = "";
    }
}
function completeTodo(li) {
    const donelist = document.getElementById("done-list");
    const completeButton = li.querySelector(".greenbutton");
    if (completeButton) {
        li.removeChild(completeButton);
    }
    const deleteButton = document.createElement("button");
    deleteButton.classList.add("redbutton");
    deleteButton.innerText = "삭제";
    deleteButton.addEventListener("click", () => removeTodo(li));
    li.appendChild(deleteButton);
    donelist.appendChild(li);
}
function removeTodo(li) {
    li.remove();
}
