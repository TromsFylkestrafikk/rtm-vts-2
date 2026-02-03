<script setup>
import { ref, computed } from "vue"

import TaskForm from "./components/TaskForm.vue"
import TaskList from "./components/TaskList.vue"
import TaskFilter from "./components/TaskFilter.vue"

// ---- State ----
const tasks = ref([
  {
    id: 1,
    title: "Learn Vue basics",
    status: "open",
    priority: "high",
  },
])

const activeFilter = ref("all")

// ---- Computed ----
const filteredTasks = computed(() => {
  if (activeFilter.value === "all") {
    return tasks.value
  }
  return tasks.value.filter(
    (task) => task.status === activeFilter.value
  )
})

// ---- Methods ----
function addTask(newTask) {
  tasks.value.push({
    id: Date.now(),
    ...newTask,
  })
}

function updateTask(updatedTask) {
  const index = tasks.value.findIndex(
    (task) => task.id === updatedTask.id
  )
  if (index !== -1) {
    tasks.value[index] = updatedTask
  }
}

function markDone(taskId) {
  const task = tasks.value.find((t) => t.id === taskId)
  if (task) {
    task.status = "done"
  }
}
</script>

<template>
  <main>
    <h1>TODO / Case Management</h1>

    <TaskForm @add-task="addTask" />

    <TaskFilter v-model="activeFilter" />

    <TaskList
      :tasks="filteredTasks"
      @update-task="updateTask"
      @mark-done="markDone"
    />
  </main>
</template>

<style scoped>
main {
  max-width: 600px;
  margin: 2rem auto;
  font-family: sans-serif;
}
</style>
